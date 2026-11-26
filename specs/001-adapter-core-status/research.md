# Research: Adapter Core and Status

All "NEEDS CLARIFICATION" items are resolved. Open questions Q1 to Q5 are resolved (2026-11-25). Source of decisions: `docs/design-brief.md` §4 to §9. This file does not change them.

## Checked on this machine

- `python3 --version` shows `Python 3.15.2`.
- `claude --help` shows these flags (checked): `-p/--print`, `--output-format text|json|stream-json`, `--input-format`, `--allowedTools`, `--disallowedTools`, `--tools`, `--model`, `--restricted`, `--strict-mcp-config`, `--mcp-config`, `--json-schema`, `--no-session-persistence`, `--permission-mode`, `--add-dir`, `--append-system-prompt`, `--max-budget-usd`, `--restricted`. There is no `--max-turns` flag in this help output. The plan does not use it. The flag `--max-budget-usd <amount>` is present (checked 2026-11-25). The plan passes it when the config key `max_budget_usd` is set.
- `claude --help` (checked 2026-11-25): `--permission-mode` choices are `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`. `dontAsk` exists. `--add-dir <directories...>` exists. `--restricted` "confines the file tools to the working directories (`--add-dir` included)", removes Bash and other code-running tools unless `--tools` names them, and ignores user, project, and local settings files. `--permission-prompts none` exists (anything that would prompt is denied). The help text does not show the permission rule syntax. See D8 and A8.
- `security` and `launchctl` exist (`/usr/bin/security`, `/bin/launchctl`).
- `slack_bolt`, `pyyaml`, `pytest` are not installed in the system Python. The plan installs nothing now. The implement step must create a venv.
- `~/.pipe/` does not exist yet.

## Decisions

### D1. Python floor
- Decision: floor is the local version, Python 3.15 (as the task requires). Use only common stdlib. Use `from __future__ import annotations`.
- Rationale: the owner machine runs 3.15.2. Python 3.15 is also what wiz-review runs here.
- Alternatives: floor 3.9 for old laptops. Rejected: no known need. Can be lowered later because the code uses no new syntax.

### D2. Patterns copied from wiz-review (0.12.0, `bin/wiz_review.py`)
Copy the idea and re-write in `pipe`. Do not import and do not edit wiz-review.
- **Launcher** (`LAUNCHER`, `install_launcher`, `launcher_target`): a small file `~/.pipe/bin/pipe` that picks the newest installed version and `exec`s it. launchd points at the launcher, so an update does not break the job.
- **launchd plist** (`launchd_plist`, `_plist_path`, `plist_is_current`): a plist in `~/Library/LaunchAgents/`, `launchctl bootstrap` / `bootout` with `gui/<uid>`. Change: wiz-review uses `StartInterval` (periodic tick). `pipe` needs a long Socket Mode connection, so the plist uses `KeepAlive` + `RunAtLoad` (D3).
- **Tick**: wiz-review `tick()` is one pass that is safe to run again and isolates errors per item ("one broken MR must not starve the others"). `pipe` copies this for the catch-up pass at start and after each Socket Mode reconnect (`catch_up()`): idempotent, one error per channel does not stop the others.
- **Doctor** (`doctor()`): list of `line(good, text)` checks, print pass or fail, exit code 1 if one fails, all checks run even after a failure. `pipe doctor` has the five checks of FR-013 (token, slack, claude, launchd, owner).
- **State** (`_atomic_write`, `load_state`, `save_state`): write a temp file, then `os.replace`. Home dir from an env var (`PIPE_HOME`, default `~/.pipe`) for tests.
- **`claude -p` call** (`review_cmd`, `claude_pass`): fixed command list, prompt on stdin, `--output-format json`, `--restricted`, `--strict-mcp-config`, `--tools`, `--allowedTools`, `--model` only if set, `subprocess.run(..., timeout=...)`, secrets removed from the child env.
- **Secret scrub** (`SECRET_RES`, `scrub`): token-like regex list and replace with `[redacted]`. `pipe` copies the list and adds Slack token forms. Also redacts the exact values of the agent's own tokens.
- **Tests**: wiz-review keeps a `tests/stub_claude/claude` stub script. `pipe` uses the same idea for one integration test of `runtime_claude.py`.

### D3. Process model
- Decision: `pipe run` is one long process. launchd plist: `RunAtLoad` true, `KeepAlive` true, `ThrottleInterval` 10, log to `~/.pipe/logs/adapter.log`.
- Rationale: Socket Mode needs an open WebSocket. KeepAlive restarts after a crash or sleep failure.
- Reconnect: the `slack_sdk` Socket Mode client reconnects by itself after a link loss. A mention that arrives during the gap is not delivered again. So the adapter runs `catch_up()` after each reconnect, not only at start (FR-004). The pass is idempotent (D6), so a repeat is safe. The adapter registers one listener on the Socket Mode client and puts a `catch_up` job on the worker queue. The queue has at most one pending `catch_up` job (no pile-up). Assumption A7.
- Alternatives: periodic tick only (wiz-review style). Rejected: no live events and slower replies.

### D4. Tokens
- Decision: two Keychain items per agent. Config value `slack_tokens: keychain:pipe-coder-pavlo` is a service-name prefix. Items: service `pipe-coder-pavlo`, account `bot` (token `xoxb-...`) and account `app` (token `xapp-...`, scope `connections:write`). Read with `security find-generic-password -s <service> -a <account> -w`. Write with `security add-generic-password -U -s ... -a ... -w ...` (done by the owner once; quickstart shows it).
- Rationale: Socket Mode needs the app-level token and the bot token. The brief shows one `keychain:` value, so one prefix covers both.
- Alternative: one JSON blob in one item. Rejected: harder to rotate one token.
- Note: a launchd job can read the login Keychain after the user logs in. The first read may show a Keychain prompt. See "Cannot verify" below.

### D5. Slack events and scopes
- Decision: subscribe to the `app_mention` event only. Bot scopes: `app_mentions:read`, `chat:write`, `channels:history`, `channels:read`, `metadata.message:read` (the status query reads message metadata of bot messages with `include_all_metadata`; assumption A3). For private channels add `groups:history`, `groups:read`. `files:write` is needed by `Transport.upload_file` (FR-024, added 2026-11-26). Catch-up also uses `conversations.history`, `conversations.replies`, `users.conversations`, `auth.test`.
- Rationale: brief §6 says act only on a direct mention.
- Dedupe: Socket Mode delivers `event_id` in each envelope. Keep a bounded set of seen `event_id` values and a set of handled mention keys `"<channel>:<ts>"` (both live path and catch-up path use the mention key). The `event_id` set stops a Slack retry. The mention key set stops a catch-up from answering a mention that live delivery already handled (FR-005).
- In-flight rule: at receipt, the adapter puts the `event_id` and the mention key in an in-memory in-flight set only. It writes them to `seen.json` after the reply or the failure message is posted. If the process crashes between receipt and reply, `seen.json` has no entry, so the restart answers the mention once. The check "a bot reply exists after the mention" in `pick_missed` stays as the guard against a duplicate.

### D6. Catch-up
- Decision: at start and after each Socket Mode reconnect (D3), `catch_up()` works per channel. It runs on the worker queue, so it never runs together with a live reply. Each missed mention goes through `should_handle`, like a live mention: a missed "who works on what?" gets the status branch (D10), not a runtime call. Source: `users.conversations` (channels the bot is in).
  1. Read `conversations.history(oldest = last_seen_ts - 7 days)` with cursor pagination. The older `oldest` finds parent messages that are older than `last_seen_ts` but have new replies.
  2. Select parents with `latest_reply > last_seen_ts` (and top-level messages with `ts > last_seen_ts`). The pure function `parents_to_scan` does this.
  3. For each selected parent, call `conversations.replies(oldest = last_seen_ts)` with cursor pagination.
  4. Keep messages with `ts > last_seen_ts` that contain `<@bot_user_id>`, are not in the handled set (`handled` = `mention_keys` plus `in_flight`), and have no reply by the bot after them (`pick_missed`).
  5. Answer oldest first. After each reply, save `last_seen_ts` (max handled `ts`, forward only).
- Reason: `history` filters by the parent `ts`. A new mention in an old thread has an old parent `ts`, so `oldest = last_seen_ts` alone would miss it.
- `last_seen_ts` is global per agent (one file), not per channel, to match the spec ("last seen message time"). Advance it only after the reply is posted (live path and catch-up path), so a crash repeats the work and the handled set and the bot-reply check stop a double reply. The live path also saves `last_seen_ts` (forward only) after each reply.
- First start (no file): `last_seen_ts` = start time. The adapter does not answer old history. (Assumption A6.)
- If Slack history no longer holds the mention, nothing is found. This is allowed by SC-002 ("if Slack history still has them").

### D7. Runtime call
- Decision: command (built by `runtime_claude.build_cmd`):
  `claude -p --output-format json --json-schema <schema> --no-session-persistence --strict-mcp-config --restricted --permission-mode dontAsk --tools <list> [--allowedTools <rules>] [--add-dir <root>...] [--disallowedTools <deny_rules>] [--model <m>]`.
- `--restricted` and `--permission-mode dontAsk` are passed for every run, owner and non-owner (one rule; D8).
  The prompt goes to stdin. `cwd` = first path of `runtime.claude.repo_roots`. Timeout = `step_timeout_min`. When `max_budget_usd` is set, the command also has `--max-budget-usd <amount>`.
- Child environment: the adapter sets `PIPE_RUNTIME=1`. The owner's Claude Code hooks fire inside the `claude -p` child. The hook exits 0 at once when `PIPE_RUNTIME` is set and non-empty, so the child session posts no status (D9).
- The prompt has: a fixed instruction, then the thread messages inside a block that is labeled untrusted data (principle V), then the task line. It has no `hop`, trust, or Slack data (FR-012). Only user text and user display names go in.
- Output: JSON schema forces `{text, status, next?, artifacts}` (brief §5.1). Only `text` and `status` are used in 001. `next` and `artifacts` are parsed and kept, but 001 ignores them (interface open for specs 002 to 005). The `--output-format json` result envelope holds the structured output; the exact envelope field is checked by the first integration test against the real `claude` (Assumption A2).
- Failure (non-zero exit, timeout, bad JSON, `status: failed`): post "I could not finish this task. Reason: <short reason>." in the thread (FR-014). The reason is scrubbed and cut to 200 characters.
- Concurrency: one worker thread and a queue. A mention that arrives while the agent is busy waits in the queue (edge case in spec). No second runtime process at the same time.
- Alternatives: Agent SDK. Rejected by the brief (decision 3).

### D8. Tool limits
- Decision: pure function `tools_for`. It sits in `src/pipe/runtime_claude_tools.py` (a `claude` adapter module, not in `core/`: it works with runtime tool names). The type `ToolPolicy` sits in the same module. The core gives only `RuntimeInput.requester_is_owner` (from the core function `is_owner(sender_id, owner)`). Signature: `tools_for(requester_is_owner, owner_tools, deny_rules)`. Owner sender (`requester_is_owner` true): tools taken from the config key `runtime.claude.owner_tools` (list, default `Read, Grep, Glob`: read-only). The owner can widen the list in config. The owner command also has `--disallowedTools` with every entry of the effective deny list (`effective_deny_rules`: the default `Bash(git push:*)` is always present, and the entries of `runtime.claude.deny_rules` are added; the owner cannot remove the default). This keeps `git push` denied if the owner adds a scoped `Bash` entry to `owner_tools` (FR-019). Specs 003 and 004 read the same key. Any other sender: an empty tool set. The command has `--tools ""` and nothing else about tools (no `--allowedTools`, no `--add-dir`, and no deny rule, because the tool set is empty). The agent answers from the thread text only. `--strict-mcp-config` with no `--mcp-config` in both cases, so no MCP server of the owner is reachable.
- If `owner` is missing or empty, `is_owner` is false for every sender, so every sender gets the empty tool set (fail closed).
- Path limit for the owner run (E17, accepted MVP risk). Flags chosen: `--restricted --permission-mode dontAsk --tools Read,Grep,Glob --allowedTools "Read(//<root>/**)" "Grep(//<root>/**)" "Glob(//<root>/**)"` for each entry of `runtime.claude.repo_roots` (`~` expanded to an absolute path), and `--add-dir <root>` for each entry after the first (the first is `cwd`). Items of `runtime.claude.owner_tools` that are not `Read`, `Grep`, or `Glob` go to `--allowedTools` as bare names (the owner chose them; they are not path-limited).
- What blocks `~/.ssh`: an allow rule alone does not block a read, because `Read` needs no prompt inside the working directories, and the allow rules only add the extra roots. The block comes from two controls. (1) `--restricted` confines the file tools to the working directories and the `--add-dir` directories (checked in `claude --help`). (2) `--permission-mode dontAsk` denies any call that no allow rule covers, so a read outside the roots is denied, not prompted (`dontAsk` is a value of `--permission-mode` in `claude --help`). Both controls are checked in `--help` text only; the real run check is in T051. A path deny list (`--disallowedTools` for `~/.ssh/**`, `~/.aws/**`, `~/.gnupg/**`, `~/.config/**`, `~/.pipe/**`, `**/.env*`) is not used: a deny-by-default mode exists, and a deny list is the weaker control (it misses every path that it does not name). Add it only if T051 shows that the two controls do not block.
- Residual risk (plan Complexity Tracking): the thread text of other people goes into the owner run. A secret inside a repo root can reach a reply. `scrub` removes only token-like strings.
- `--restricted` rule: passed for every run. The help text says it confines file tools to the working directories and ignores user, project, and local settings files. The owner hooks in settings do not run in the child; the `PIPE_RUNTIME` guard stays as a second control.
- Rationale: brief §8. The old rule gave non-owners read-only `Read`, `Grep`, `Glob`. That rule let a colleague read files such as `~/.aws/credentials` or `~/.ssh`. File access for other people comes only with delegation in a later spec (M3), in a worktree.
- The config key `owner` (Slack user ID) is accepted. Brief §5.4 lists it.
- Resolved 2026-11-25 (Q1): accept the `owner` config key.
- Resolved 2026-11-25 (Q5): a non-owner mention runs the runtime with no tools (`--tools ""`).
- This meets the constitution rule (1.0.1): a non-owner task runs with an allowed-tools list for its kind, or with no tools.

### D9. Status hooks
- Hook input format: Claude Code runs a hook command and sends one JSON object on stdin. Local evidence: the test fixtures of the installed `security-guidance` plugin (`~/.claude/plugins/cache/claude-plugins-official/security-guidance/2.0.20/tests/conftest.py`) build payloads with the keys `session_id`, `hook_event_name`, `cwd` (and `stop_hook_active` for `Stop`). The plan uses only `session_id`, `hook_event_name`, `cwd`. Other keys are ignored. The official docs were not found locally. This is an assumption (A1).
- `Stop` fires when Claude Code finishes a reply turn, not when the session ends. `SessionEnd` fires when the session ends. 001 uses all three events: `SessionStart`, `Stop`, `SessionEnd`.
- Resolved 2026-11-25 (Q2): add a `SessionEnd` hook. `SessionStart` gives stage `started`, `Stop` gives `idle`, `SessionEnd` gives `stopped`.
- Decision: `pipe-status-hook <event>` reads stdin JSON and does:
  1. Key = `session_id`. State file `~/.pipe/status/<session_id>.json` holds `{channel, ts, repo, branch, stage, blocker, started_at, updated_at}`.
  2. `SessionStart`: no state file → `chat.postMessage` to `#pipe-status` with `metadata`; save `channel` and `ts`. Stage `started`.
  3. `Stop`: state file exists → `chat.update` the same `ts`. Stage `idle`. If the file is missing (hook lost), post once and save. One session always gives one message (SC-003).
  3a. `SessionEnd`: same as `Stop`, but the stage is `stopped`. A later `SessionStart` for the same `session_id` sets `started` again (in place).
  3b. Each `chat.update` and each post writes `updated_at` (epoch seconds) into the metadata (D10).
  3c. If the environment variable `PIPE_RUNTIME` is set and non-empty, the hook exits 0 at once. It reads no stdin, calls no Slack API, and writes no file.
  3d. Lock: before the first post for a `session_id`, the hook creates `~/.pipe/status/<session_id>.lock` with `os.open(..., O_CREAT | O_EXCL)`. If the lock exists, the hook waits (up to 5 seconds) for the state file and then does `chat.update`. The hook removes the lock after it saves the state file. The hook owns lock cleanup: before it creates a lock, it removes a lock whose file mtime is older than 30 seconds (stale). The adapter does not touch lock files. Two concurrent first calls post one message.
  3e. The hook takes an injected function `call_slack(method, payload) -> dict`. The default uses `urllib.request` with a 5 second timeout. Tests pass a recording fake (`FakeCallSlack`).
  4. Never block Claude Code. The script catches all errors, writes a line to `~/.pipe/logs/hook.log`, and exits 0. Network timeout 5 seconds.
- Fields: `who` = `agent_name` from config; `repo` = base name of the git top-level of `cwd` (`git rev-parse --show-toplevel`, fallback to the base name of `cwd`); `branch` = `git rev-parse --abbrev-ref HEAD`; `repo` and `branch` pass through `scrub` and `escape_mentions`; `stage` from the event; `blocker` = empty ("none"). Hook input has no blocker.
- Resolved 2026-11-25 (Q3): no blocker command in 001. The blocker stays "none". This is a known limit. Add a command later if people ask.
- "One thread per session": the status message is the thread root. 001 posts no thread replies. The message is updated in place. (The brief says "one thread per session, uses `chat.update`"; one root message that is updated meets both.)
- Runtime rule: the hook runs with the venv Python through the launcher `~/.pipe/bin/pipe`, like the adapter. It may import `pyyaml` and `pipe.*` modules (config, state, keychain, `core.scrub`, `core.status`). It does not import `slack_bolt` or `slack_sdk`. It calls `https://slack.com/api/chat.postMessage` and `chat.update` through `call_slack` (default: `urllib.request`). It reads the bot token from the Keychain with `security`, and the config with `load_config` (`agent_name`, `status_channel`, `slack_tokens`).
- Channel ID cache: `~/.pipe/state.json`, key `status_channel_id` (shared with the adapter). The hook uses the channel name `#pipe-status` (config `status_channel`) until the ID is cached. After the first `chat.postMessage`, it writes the channel ID from the Slack response to `state.json` (atomic write, only this key). The adapter writes the same key after `conversations.list`.
- Alternatives: import `slack_sdk` in the hook (slower start). Rejected.
- Hook registration: the owner adds `SessionStart`, `Stop`, and `SessionEnd` hooks to `~/.claude/settings.json`. The adapter does not edit that file. The quickstart gives the JSON to copy. Command: `~/.pipe/bin/pipe status-hook SessionStart`.

### D10. Status message format and the "who works on what?" query
- Message `metadata`: `event_type = "pipe.status.v1"`, `event_payload = {v, session_id, who, repo, branch, stage, blocker, started_at, updated_at}`. `updated_at` is epoch seconds (integer). Each `chat.update` sets it again. The status message is not a task, so it uses a separate event type, not `pipe.task.v1`. This is data only. See [contracts/status-hook.md](contracts/status-hook.md).
- The text of the message is a readable line made from the same fields (for people).
- Query: one match rule. After the bot mention (`<@bot_user_id>`) is removed, the text contains `who works on what` as a case-insensitive substring. The pure function `is_status_query(text)` does this. The adapter calls `conversations.history(channel=#pipe-status, oldest=now-7d, include_all_metadata=true)` with cursor pagination (more than 100 messages), keeps messages that have `bot_id` set and `event_type == "pipe.status.v1"` (`parse_status_messages`), runs `recent(statuses, now)`, and posts a summary built by `render_summary`.
- Trust (plan Complexity Tracking, principle V): agent cards start in spec 002. 001 reads the status metadata as display data only. It accepts only messages with `bot_id`, validates the field types and the `stage` enum, escapes Slack mention syntax (`<!channel>`, `<!here>`, `<!everyone>`, `<@U…>`, `<!subteam^…>`) in all fields, passes the summary through `scrub`, and never uses the data as a command. No runtime call is needed for this answer (faster, cheaper, testable). The query reads 7 days of history because `oldest` filters by message `ts`, and a message update does not change its `ts`.
- `recent` keeps a status when `updated_at` (from the metadata) is in the last 24 hours. It does not use the message `ts`. A session that started more than 24 hours ago and is still active stays in the answer.
- Resolved 2026-11-25 (Q4): each `chat.update` writes `updated_at` into the metadata. The filter uses it.
- Ceiling: a message older than 7 days (by `ts`) is not read, even if it was updated later. Status files older than 7 days are cleaned (D11), so this matches.
- The `#pipe-status` channel is found by name (`conversations.list`, method `Transport.find_channel`, task T025) once and cached in `~/.pipe/state.json`.

### D11. Local state files (`~/.pipe/`)
- `config.yaml` — owner config (brief §5.4 + `owner`, the section `runtime.claude` with `owner_tools`, `repo_roots`, and `deny_rules`, `max_budget_usd`, `status_channel`, `model`).
- `state.json` — `{last_seen_ts, bot_user_id, status_channel_id}`.
- `seen.json` — bounded list: last 500 `event_id`, last 500 mention keys. The adapter writes it after the reply or failure message, not at receipt (D5).
- `status/<session_id>.lock` — short-lived lock file of the hook. The hook removes it after the first post, and removes a stale one (mtime older than 30 seconds). No other code touches it (D9).
- `status/<session_id>.json` — per session; the adapter deletes it at start when its file mtime is older than 7 days (the file is written on each event, so this means 7 days with no event).
- `logs/`, `bin/pipe`.
- All writes are atomic (D2). Files have mode 0600. No token in any file.

### D12. Testing
- `pytest`. Unit tests for every `core/` module are written first (principle VII). `tests/fakes.py` has `FakeTransport` (records posts, serves history) and `FakeRuntime` (returns a canned `RuntimeOutput`).
- Unit tests for `tools_for` (argument `requester_is_owner`) cover: owner gets `runtime.claude.owner_tools` (default `Read, Grep, Glob`) and `disallowed` = `effective_deny_rules(deny_rules)` (the default is always in it; a custom list adds to it); non-owner gets an empty tool set with no deny rule; empty `owner` gives the empty tool set. A unit test for `build_cmd` checks that an empty tool set gives `--tools ""`, that every command has `--restricted` and `--permission-mode dontAsk`, and that the owner command has the path allow rules and `--add-dir` for `runtime.claude.repo_roots`, and `--disallowedTools` with the effective deny list (the non-owner command has none). Unit tests for `status` cover `SessionEnd` → `stopped`, `updated_at` set on each update, and `recent` by `updated_at` (an old `ts` with a new `updated_at` is kept).
- Integration tests (with fakes) cover: a mention while the link is down → reconnect → one reply; a non-owner asks to read a local file → the runtime has no tools and reads nothing; mention → one reply; same event twice → one reply; restart after a reply → no second reply; catch-up reply; runtime failure message; token in reply is scrubbed; status start/stop/end → one message updated; crash after enqueue and before reply → restart answers once; new mention in an old thread → answered; more than 100 history messages → all read; a non-bot poster of status metadata → ignored; the hook exits at once when `PIPE_RUNTIME` is set and non-empty, and runs when it is empty; a stale lock (older than 30 seconds) is removed by the hook; two concurrent first hook calls → one message.
- One test uses a stub `claude` script on `PATH` to check `build_cmd` and the output parse.
- No test calls real Slack or real Claude. A manual check is in [quickstart.md](quickstart.md).

### D13. Dependencies and reasons
| Dependency | Why |
|---|---|
| `slack_bolt` | Socket Mode and event handling (constitution). It brings `slack_sdk` for `WebClient`. |
| `pyyaml` | Read `config.yaml` (constitution). |
| `pytest` (dev only) | Tests (task input). |
No other dependency. The hook and the Keychain, launchd, and runtime code use the standard library.

### D14. Transport port and the Slack adapter modules (principle XI, version 1.2.0)
- Decision: the core talks to the chat system only through `ports.Transport`. The old `SlackPort` is this port. Its operations are the ones that specs 001 to 004 already use ([contracts/transport.md](contracts/transport.md)). The Slack adapter has four modules: `transport_slack.py` (WebClient), `transport_slack_events.py` (`slack_bolt` Socket Mode handlers and the reconnect listener), `transport_slack_map.py` (pure mapping, Block Kit, mention syntax), and `transport_slack_http.py` (the `urllib` `call_slack` of the status hook). `FakeTransport` is the in-memory double (the former `FakeSlack`).
- The adapter maps Slack fields to `sender_id`, `sender_is_bot`, and `sender_handle`. The core trust rules use these names and `card_owner_id`. Mention syntax and its escape sit in the adapter (`Transport.mention`, `Transport.escape_mentions`). Core text builders get them as a `Formatter`.
- The status hook is not core. It imports `transport_slack_http` (urllib only), so it keeps its fast start and imports no `slack_bolt` and no `slack_sdk`.
- Rationale: one chat product must not shape the core. A new transport needs no core change. The cost is one port and one mapping module.
- Alternatives: keep Slack names in the core and only hide `slack_bolt`. Rejected: the trust rules would still read Slack fields. Add operations for Discord or Telegram now. Rejected: YAGNI (one line: future adapters).

### D15. Decisions of 2026-11-26, second batch (constitution 1.3.0)
- **N1. `deny_rules` is a union.** The default `Bash(git push:*)` is ALWAYS in the effective deny list. The config key `runtime.claude.deny_rules` (default `[]`) only adds rules. Pure function `effective_deny_rules`. Rationale: principle IV. A typo or a custom list must not remove the push guard. Rejected: "a custom list replaces the default" (the old FR-019 text).
- **N2. `Transport.upload_file`.** Artifacts such as screenshots and reports need a file upload. Slack uses `files_upload_v2` and the scope `files:write`. The link goes to `artifacts`. The default upload root is `~/.pipe/run/`. This default is a fail-closed choice of the spec author. The owner must confirm it (open question U1 in the report of this pass).
- **N3. Runtime status `waiting` and `proposal`.** 001 only parses them. Spec 003 gives them meaning (dialog step, plan proposal).
- **N4. `pipe flows`.** Spec 001 owns the command table. Spec 006 owns the handler.

## Cannot verify on this machine

- A1: the exact hook stdin keys (see D9). Official docs not found locally.
- A2: the exact shape of the `claude -p --output-format json --json-schema` result envelope (which field holds the structured output). wiz-review `extract_findings` reads it; the implement step copies that parse and checks it with a real run.
- A3: Slack workspace setup: bot scopes (including `metadata.message:read`: not checked that this scope is needed or enough to read metadata through `conversations.history` with `include_all_metadata`), `#pipe-status` and `#pipe-work` channels, the bot in the channels. No Slack access here.
- A4: a launchd job reading the login Keychain without a prompt.
- A6: first start with no `last_seen_ts` answers no old history. The spec Assumptions now state this rule.
- A5: the `slack_bolt` version and its Socket Mode extras. Not installed. Pin at implement time.
- A7: `slack_bolt` Socket Mode reconnect. `slack_bolt` is not installed, so this is not checked here. Assumption: `SocketModeHandler` wraps a `slack_sdk` `SocketModeClient` (reachable as `handler.client`); that client reconnects by itself, receives a `hello` message on each connect, and lets code add listeners (message, error, and close listener lists). The adapter registers one listener that queues `catch_up()` on each connect. The exact attribute and listener names are checked at implement time (T051). Fallback if no usable listener exists: queue `catch_up()` when the `hello` message arrives, or on a timer (every 5 minutes).
- A8: permission rule syntax. `claude --help` does not show it. Assumption: a path rule for an absolute path starts with `//` (for example `Read(//Users/me/code/**)`), and a `Read` rule also covers `Grep` and `Glob`. Also not checked by a real run: that `--restricted` with `--permission-mode dontAsk` refuses a read of `~/.ssh/config`. T051 checks both.
