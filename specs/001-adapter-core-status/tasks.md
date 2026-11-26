---

description: "Task list for Adapter Core and Status"
---

# Tasks: Adapter Core and Status

**Input**: Design documents from `/specs/001-adapter-core-status/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are required. Constitution principle VII (NON-NEGOTIABLE): every pure-function business rule has a unit test task BEFORE its implementation task. The test must fail first. Tests use fakes: no real Slack and no real Claude.

**Organization**: Tasks are grouped by user story. Paths follow the Source Code layout in [plan.md](plan.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US5, from [spec.md](spec.md)
- Test tasks start with "Write failing test".

## Path Conventions

Single project: `src/pipe/`, `tests/unit/`, `tests/integration/`, `tests/fakes.py` at the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization

- [ ] T001 Create the directories and empty `__init__.py` files from the plan: `src/pipe/`, `src/pipe/core/`, `tests/unit/`, `tests/integration/`, `tests/stub_claude/` (the directory only; T018 creates the stub script)
- [ ] T002 Create `pyproject.toml` with the dependencies `slack_bolt` and `pyyaml`, the test dependency `pytest`, and the entry point `pipe` for `pipe.cli:main`. Create a venv (the implement step does this; research.md "Checked on this machine")
- [ ] T003 [P] Create `tests/conftest.py` with a fixture that sets `PIPE_HOME` to a temporary directory (research.md D2 "State")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config, state, contract types, ports, and fakes that every story needs

**CRITICAL**: No user story work starts before this phase is complete.

- [ ] T004 [P] Write failing test for config load and validation in `tests/unit/test_config.py`:
  - `agent_name` is required.
  - `slack_tokens` has the format `keychain:<service>`. A value that looks like a token (`xox`, `xapp`) is rejected.
  - `owner` is accepted (Slack user ID). `validate_config` returns a warning when `owner` is empty.
  - `runtime.claude.owner_tools` is a list of non-empty strings. The default is `[Read, Grep, Glob]`. A wider list is accepted.
  - `max_budget_usd` is optional, default unset. A value of 0 or less is rejected.
  - `runtime.claude.repo_roots` default is `[~/code]` (`~` expanded). A wrong type is an error.
  - `runtime.claude.deny_rules` default is `[]`. It is a list of non-empty strings (extra rules). A wrong type or an empty string is an error. The default `Bash(git push:*)` is not in the config: it is added by `effective_deny_rules` (T057, FR-019).
  - The old top-level keys `owner_tools` and `repo_roots` are an error. The message names the new path `runtime.claude.<key>`. There is no fallback.
  - Other keys under `runtime` (`name`) are accepted and ignored in 001 (spec 003 adds them). Spec 003 and spec 004 read `deny_rules` from 001 and do not define it again.
  - `status_channel` default is `pipe-status`.
  - `model` matches `^[A-Za-z0-9][A-Za-z0-9._\[\]-]*$`. It is passed only if set.
  - `step_timeout_min` default is 30. The minimum is 1.
  - `allowlist` and `exposed` are accepted and ignored.
- [ ] T005 Implement `load_config` and the pure `validate_config` in `src/pipe/config.py` (data-model.md "Agent (config)"). Include the section `runtime.claude` (`owner_tools`, `repo_roots`, `deny_rules`), the error for the old top-level keys, `max_budget_usd`, and the empty-`owner` warning (T004)
- [ ] T006 [P] Write failing test for state files in `tests/unit/test_state.py`:
  - Atomic write: temp file, then `os.replace`.
  - File mode is 0600.
  - `PIPE_HOME` override works.
  - `last_seen_ts` moves forward only.
  - First start sets `last_seen_ts` to the start time (A6).
  - `seen.json` keeps the last 500 `event_ids` and the last 500 `mention_keys`.
  - Writing `status_channel_id` to `state.json` keeps the other keys.
- [ ] T007 Implement `~/.pipe/` file read and write in `src/pipe/state.py` for `state.json`, `seen.json`, and `status/<session_id>.json` (data-model.md LocalState, SeenSet, SessionStatus)
- [ ] T008 [P] Write failing test for the runtime contract types in `tests/unit/test_contract.py`:
  - `parse_output` accepts a valid `{text, status, next?, artifacts}`.
  - It raises `RuntimeFailed` for invalid JSON, a missing `text`, and a `status` outside `done | needs_approval | waiting | failed | delegate`.
  - `next` and `artifacts` are parsed and kept. `data` (an object) is parsed and kept. A `data` that is not an object raises `RuntimeFailed`.
- [ ] T009 Implement the dataclasses `RuntimeInput` (fields `thread`, `task`, `requester_is_owner`, optional `request`), `RuntimeOutput` (with the optional `data`), the neutral `Message`, `Identity`, `Button`, `MentionEvent`, `ThreadTask`, `SessionStatus`, the exception `RuntimeFailed`, and `parse_output` in `src/pipe/core/contract.py` (contracts/runtime-contract.md; contracts/transport.md; data-model.md). `ToolPolicy` is NOT defined here: it belongs to the `claude` adapter (T023). The module has no tool name and no chat field
- [ ] T010 [P] Implement the Protocols `Transport`, `RuntimePort`, and `Formatter` in `src/pipe/ports.py` with the operations of contracts/transport.md (`whoami`, `find_channel`, `member_channels`, `post_message`, `update_message`, `delete_message`, `history`, `replies`, `pin`, `list_pins`, `send_dm`, `on_event`, `on_reconnect`, `mention`, `escape_mentions`, `id_pattern`). Add no operation for another chat product. `ports.py` imports no chat library
- [ ] T011 [P] Implement `src/pipe/keychain.py`: wrapper over `security find-generic-password -s <service> -a <account> -w` for the accounts `bot` and `app` (research.md D4). It never logs a token value
- [ ] T012 Implement `FakeTransport`, `FakeCallSlack`, `FakeRuntime`, and `FakeKeychain` in `tests/fakes.py` (depends on T009, T010). `FakeTransport` is the in-memory `Transport` and the one test double for the chat system (the former `FakeSlack`, renamed). It needs no Slack library:
  - `FakeTransport` records posts and updates. It serves history and replies with cursor pagination (page size 100, `next_cursor`). It sets `sender_is_bot` and `sender_id` on bot messages and `latest_reply` on parents. It implements `mention` and `escape_mentions` with a simple fake syntax (`<@id>`).
  - `FakeTransport` has `find_channel(name)` (returns a canned channel ID) and `on_reconnect(callback)`. `FakeTransport.reconnect()` calls the registered callbacks (simulates a Socket Mode reconnect). `FakeTransport` can hold messages that arrive while the link is "down" and serve them in history after `reconnect()`.
  - `FakeCallSlack` is the recording fake of the hook function `call_slack(method, payload)`. It records each `(method, payload)`, returns a canned `{ok, channel, ts}`, and can raise an error or a timeout on demand.
  - `FakeRuntime` returns a canned `RuntimeOutput`. It records its `RuntimeInput`.
  - `FakeKeychain` returns canned tokens.
- [ ] T013 Create the `pipe` command dispatcher in `src/pipe/cli.py` with the sub-commands `run`, `doctor`, `schedule`, `status-hook`. Each sub-command is a stub that later phases fill (contracts/cli.md)

- [ ] T053 [P] Write failing test for the Slack mapping in `tests/unit/test_transport_slack_map.py` (FR-020, FR-021, contracts/transport.md):
  - A Slack message with `bot_id` gives `sender_id` = `bot_id`, `sender_is_bot` true, and `sender_handle` = `user`. A message with no `bot_id` gives `sender_id` = `user` and `sender_is_bot` false.
  - `event_id` comes from the envelope. A catch-up message has `event_id` `None`.
  - `metadata` and `reactions` map to the neutral fields. `ts` and `thread` map as strings.
  - `buttons` map to a Block Kit `actions` block (`action_id`, `label`). No button gives no block.
  - `mention("U1")` gives `<@U1>`. `escape_mentions` escapes `<!channel>`, `<!here>`, `<!everyone>`, `<@U123>`, and `<!subteam^S1>`. Plain text stays the same.
  - `id_pattern` accepts `B012ABCDEF`, `U034GHIJKL`, `W1AB` and rejects `pavlo` and `b012`.
  - The module imports no `slack_bolt` and no `slack_sdk`.
- [ ] T054 [P] Implement the pure mapping in `src/pipe/transport_slack_map.py` (T053): Slack message to `Message`, buttons to Block Kit, `mention`, `escape_mentions`, `id_pattern`
- [ ] T055 Implement the Socket Mode handlers in `src/pipe/transport_slack_events.py` (depends on T054, T010; I/O, so no unit test, T051 and T052 check it by hand): `app_mention` gives a `MentionEvent` with the `event_id` of the envelope. Spec 003 adds `reaction_added` (`ReactionEvent`) and `block_actions` (`ClickEvent`). One listener on the Socket Mode client calls the `on_reconnect` callbacks (research.md A7). This is the only module of the adapter that imports `slack_bolt`
- [ ] T056 [P] Write failing contract test for `Transport` in `tests/unit/test_transport_contract.py` (contracts/transport.md). One test class runs against `FakeTransport` and against the Slack `Transport` with a stub `WebClient`:
  - `post_message` in a thread returns a `ts`. `replies` returns it with its `metadata` and `reactions`.
  - `update_message` and `delete_message` change the stored message.
  - `history` and `replies` read more than 100 messages through the cursor and give each message once.
  - `pin` and `list_pins` give the pinned `ts`.
  - `send_dm` posts one message to the user and returns nothing.
  - `on_event` handlers get neutral events. `on_reconnect` callbacks run after `reconnect()`.
  - No call needs `users.info` or `bots.info`.
- [ ] T059 Write failing test for `Transport.upload_file` in `tests/unit/test_transport_contract.py` (same file as T056, so it is not parallel with T056; FR-024, SC-011, decision N2). One test class runs against `FakeTransport` and against the Slack `Transport` with a stub `WebClient`:
  - `upload_file(channel, thread, name, data, title)` with `bytes` returns an `https://` link. The Slack stub gets one `files_upload_v2` call with the channel, the thread `ts`, the file name, and the title. No other upload API is called.
  - `data` as a `Path` to a regular file inside the upload roots gives the same result. A path outside the roots, a path of a symbolic link, a directory, and a file over 10 MB raise `UploadRefused`. The stub gets no call in these cases.
  - `name` and `title` pass `scrub`. A token-like string in `name` becomes `[redacted]`.
  - `FakeTransport.upload_file` records `(channel, thread, name, title, size)` and returns a fixed link. It records no file content.
  - The Slack adapter needs the bot scope `files:write` (checked as a text line in `quickstart.md`).
  - The upload roots default to `~/.pipe/run/`. The composition root can pass others.
- [ ] T060 Add `upload_file` to the Protocol in `src/pipe/ports.py` (same file as T010), the exception `UploadRefused` to `src/pipe/core/contract.py` (same file as T009), `FakeTransport.upload_file` to `tests/fakes.py` (same file as T012), and the Slack version to `src/pipe/transport_slack.py` (`files_upload_v2`, scope `files:write`) (T059). Add the scope to research.md D5 and to the Slack app section of `quickstart.md`
- [ ] T061 [P] Write failing test for the CLI command `pipe flows` in `tests/unit/test_cli.py` (FR-025, SC-012, contracts/cli.md):
  - The parser accepts `pipe flows`, `pipe flows show <name>`, and `pipe flows validate`, and `pipe flows validate <name>`. It rejects `pipe flows save`, `pipe flows delete`, and any other form (no write command).
  - Each form calls the injected `flows_handler(action, name)` with `action` `list`, `show`, or `validate` and returns its exit code.
  - Without a handler (spec 006 not built), the command prints `flows: not installed` and exits with code 1.
  - The command writes no file.
- [ ] T062 Add the `flows` sub-command and the dispatch to `src/pipe/cli.py` (T061; same file as T013). The handler is injected. Spec 006 supplies it
- [ ] T063 Write failing test for the new runtime output fields in `tests/unit/test_contract.py` (same file as T008; FR-026, decision N3):
  - `parse_output` accepts `status: waiting` with `reason: needs_input` and a `text` (the question).
  - It keeps an optional `proposal` (an object, at most 4000 characters as canonical JSON). A `proposal` that is not an object, or is too large, raises `RuntimeFailed`.
  - `reason` is a string of at most 200 characters, and it passes `scrub`. A `reason` on a status other than `waiting` or `failed` is dropped.
  - 001 posts `waiting` and `proposal` as text only. It starts no dialog and no plan.
- [ ] T064 Add `reason` and `proposal` to `RuntimeOutput` and `parse_output` in `src/pipe/core/contract.py` (T063; same file as T009)

**Checkpoint**: Foundation ready. User stories can start.

---

## Phase 3: User Story 1 - Mention an agent and get a reply (Priority: P1) MVP

**Goal**: A mention gives exactly one reply in the same thread. The reply has no token-like string. A non-owner sender gets a runtime with no tools.

**Independent Test**: Run `pytest tests/unit tests/integration/test_adapter_mention.py`. Then do the quickstart scenarios "1", "1 (duplicate)", "1 (scrub)", "1 (non-owner)".

### Tests for User Story 1 (write first, they MUST fail)

- [ ] T014 [P] [US1] Write failing test for `scrub` and `escape_mentions` in `tests/unit/test_scrub.py` (FR-006, SC-007, research.md D2, D10):
  - `xoxb-`, `xoxp-`, `xapp-` forms become `[redacted]`.
  - The wiz-review token patterns become `[redacted]`.
  - The exact values of the agent's own tokens become `[redacted]`.
  - Text without a token stays the same.
  - `escape_mentions` is not tested here. It is a `Transport` function. T053 tests the Slack version.
- [ ] T015 [P] [US1] Write failing test for `should_handle` in `tests/unit/test_router.py` (data-model.md MentionEvent rules 1 to 5):
  - Ignore when `sender_is_bot` is true.
  - Ignore when `sender_id` is the agent itself.
  - Ignore when `event_id` is in `event_ids` or in `in_flight`.
  - Ignore when `<channel>:<ts>` is in `mention_keys` or in `in_flight`.
  - Ignore when the text has no mention of the agent (the test passes a fake `mention` function).
  - Otherwise return `Decision(action="reply", reason)`.
  - `is_owner(sender_id, owner)` is true only when `owner` is not empty and equals `sender_id`. An empty or `None` `owner` gives false for every sender (fail closed).
- [ ] T016 [P] [US1] Write failing test for `remember` in `tests/unit/test_dedupe.py` (data-model.md SeenSet):
  - It adds keys.
  - It keeps the last 500.
  - It drops the oldest.
  - It does not change its input.
- [ ] T017 [P] [US1] Write failing test for `tools_for(requester_is_owner, owner_tools, deny_rules)` and the type `ToolPolicy` in `tests/unit/test_runtime_claude_tools.py` (FR-016, FR-019, FR-022, research.md D8). `ToolPolicy` is defined in `src/pipe/runtime_claude_tools.py`, not in `core/`:
  - `requester_is_owner` true: the `runtime.claude.owner_tools` list, `disallowed` = `effective_deny_rules(deny_rules)`, `restricted=True`. The default tools are `[Read, Grep, Glob]`. With no custom `deny_rules`, `disallowed` is `[Bash(git push:*)]`.
  - `requester_is_owner` true and `owner_tools` has a scoped `Bash(pytest:*)` entry: `Bash(git push:*)` is still in `disallowed`. A custom `deny_rules` list ADDS to the default. It never removes it (FR-019, SC-010).
  - `requester_is_owner` true and `runtime.claude.owner_tools` is widened: the wider list is used.
  - `requester_is_owner` false: `tools=[]`, `allowed=[]`, `disallowed=[]`, `restricted=True`. No `Read`, `Grep`, or `Glob`.
  - A missing or empty `owner` gives `requester_is_owner` false through `is_owner` (T015), so the empty tool set applies to every sender.
- [ ] T018 [P] [US1] Write failing test for the `claude -p` command and prompt in `tests/unit/test_runtime_claude.py`, with a stub script `tests/stub_claude/claude` on `PATH`. This task creates the stub script (T001 made only the directory):
  - `build_cmd` has the flags of contracts/runtime-contract.md.
  - Every command (owner and non-owner) has `--restricted` and `--permission-mode dontAsk`. `--restricted` is passed for every run (research.md D8).
  - Non-owner: `--tools ""` (empty value present). No `--allowedTools`, no `--add-dir`, and no deny rules: the tool set is empty, so deny rules are not needed (FR-019).
  - Owner: `--tools <list>`; `--allowedTools` has `Read(//<root>/**)`, `Grep(//<root>/**)`, and `Glob(//<root>/**)` for each `runtime.claude.repo_roots` entry (`~` expanded to an absolute path); `--add-dir <root>` for each root after the first (FR-018); `--disallowedTools` has every entry of the effective deny list (`Bash(git push:*)` always, plus `runtime.claude.deny_rules`) (FR-019). A widened `runtime.claude.owner_tools` item that is not `Read`, `Grep`, or `Glob` goes to `--allowedTools` as a bare name.
  - `--model` only if set.
  - `--max-budget-usd <amount>` only if `max_budget_usd` is set.
  - `cwd` is the first `runtime.claude.repo_roots` entry.
  - Tokens are removed from the child environment.
  - The child environment has `PIPE_RUNTIME=1` (I1).
  - The prompt wraps the thread as untrusted data. It holds no `hop`, trust, or Slack data (FR-012).
  - Timeout, non-zero exit, command not found, and bad JSON all raise `RuntimeFailed(reason)`.
- [ ] T019 [P] [US1] Write failing test in `tests/integration/test_adapter_mention.py` with `FakeTransport` and `FakeRuntime`:
  - One mention gives one reply in the same thread.
  - The same `event_id` twice gives one reply (SC-001).
  - A second event for a mention that is in flight is dropped.
  - `seen.json` gets the `event_id` and the mention key only after the reply or the failure message is posted.
  - `last_seen_ts` is saved after each reply, forward only.
  - The context has the messages of this thread only (FR-002).
  - The reply is scrubbed (SC-007).
  - A runtime failure posts "I could not finish this task. Reason: ...". The reason is scrubbed and has at most 200 characters (FR-014).
  - A second mention while the agent is busy waits in the queue.
  - A non-owner asks to read a local file such as `~/.aws/credentials`. `FakeRuntime` receives `requester_is_owner` false, and the `claude` adapter test (T018) shows the empty tool set, so no file is read (FR-016, spec User Story 1 scenario 5).
  - The adapter run loop imports no Slack module. The test builds the adapter with `FakeTransport` only (FR-020).

### Implementation for User Story 1

- [ ] T020 [P] [US1] Implement `scrub` and `escape_mentions` in `src/pipe/core/scrub.py` (T014)
- [ ] T021 [P] [US1] Implement `should_handle` and `Decision` in `src/pipe/core/router.py` (T015)
- [ ] T057 [US1] Write failing test for `effective_deny_rules(deny_rules)` in `tests/unit/test_runtime_claude_tools.py` (same file as T017; FR-019, SC-010, decision N1 of plan.md):
  - `[]` and `None` give `["Bash(git push:*)"]`.
  - A custom list `["Bash(rm:*)"]` gives `["Bash(git push:*)", "Bash(rm:*)"]`. The default is first. The order of the owner entries stays.
  - A list that holds `Bash(git push:*)` gives it once (no duplicate).
  - A list that does not name the default (also an empty list) still gives the default. The owner cannot remove it.
  - The function returns a new list and does not change its input.
  - `tools_for(True, ...)` uses it for `disallowed`. `tools_for(False, ...)` gives `disallowed=[]`.
- [ ] T058 [US1] Implement `effective_deny_rules` in `src/pipe/runtime_claude_tools.py` and use it in `tools_for` (T057; same file as T023, so it runs before T023). Specs 003 and 004 call the same function from `map_request`
- [ ] T022 [P] [US1] Implement `remember` in `src/pipe/core/dedupe.py` (T016)
- [ ] T023 [P] [US1] Implement `ToolPolicy` and `tools_for` in `src/pipe/runtime_claude_tools.py` (T017). The module is part of the `claude` adapter. It is not a core module:
  - `requester_is_owner` true gets `runtime.claude.owner_tools` (default `[Read, Grep, Glob]`) and `disallowed` = `effective_deny_rules(runtime.claude.deny_rules)` (T057, T058).
  - `requester_is_owner` false gets the empty tool set.
- [ ] T024 [US1] Implement `build_cmd`, the prompt builder, and `ClaudeRuntime.run` in `src/pipe/runtime_claude.py` (T018; depends on T009, T023). `run` calls `tools_for(inp.requester_is_owner, ...)`:
  - An empty tool set must still produce `--tools ""`.
  - Add `--restricted` and `--permission-mode dontAsk` to every command. Add the path allow rules, `--add-dir`, and `--disallowedTools` (the `deny_rules`) for the owner (T018).
  - Set `PIPE_RUNTIME=1` in the child environment.
  - Add `--max-budget-usd` when `max_budget_usd` is set.
- [ ] T025 [US1] Implement the Slack `Transport` over `slack_sdk.WebClient` in `src/pipe/transport_slack.py` (the Slack adapter; depends on T054 for the mapping): `whoami` (`auth.test`), `post_message` (`chat.postMessage`) in a thread, `replies` (`conversations.replies`) for the thread context, and `find_channel(name)` (`conversations.list`, resolves `#pipe-status`; used by T043 and T046) (depends on T010)
- [ ] T026 [US1] Implement the run loop in `src/pipe/adapter.py` (T019; depends on T020 to T025, T055):
  - Register one handler with `Transport.on_event`. The Slack Socket Mode code is in `src/pipe/transport_slack_events.py` (T055). `adapter.py` imports no Slack module. Then `should_handle`, one worker thread with a queue.
  - At receipt, add the `event_id` and the mention key to the in-memory in-flight set only.
  - `is_owner(sender_id, owner)`, `RuntimeInput.requester_is_owner`, runtime call, `scrub`, reply in the thread, failure message.
  - After the reply or the failure message is posted, call `remember` and write `seen.json`.
  - After each reply, save `last_seen_ts` (forward only).
- [ ] T027 [US1] Wire `pipe run` in `src/pipe/cli.py`: read config and Keychain tokens, build the Slack transport (the composition root: the only place that names `transport_slack`), call `whoami`, start the adapter (depends on T005, T011, T026)

**Checkpoint**: User Story 1 works alone. This is the MVP.

---

## Phase 4: User Story 2 - Pick up missed mentions after being offline (Priority: P2)

**Goal**: At start, the adapter answers mentions that it missed, also new mentions in old threads. It never answers one mention twice.

**Independent Test**: Run `pytest tests/unit/test_catchup.py tests/integration/test_adapter_catchup.py`. Then do the quickstart scenario "2".

### Tests for User Story 2 (write first, they MUST fail)

- [ ] T028 [P] [US2] Write failing test for `parents_to_scan` and `pick_missed` in `tests/unit/test_catchup.py` (research.md D6):
  - `parents_to_scan` selects parents with `latest_reply > last_seen_ts` and top-level messages with `ts > last_seen_ts`.
  - `pick_missed` keeps messages with `<@bot_user_id>` and `ts > last_ts`.
  - It drops handled mention keys. `handled` is `mention_keys` plus `in_flight`.
  - It drops a mention that already has a bot reply after it.
  - It includes thread replies.
  - It returns oldest first.
  - It ignores messages from the agent itself.
  - A mention in a thread whose parent is older than `last_seen_ts` is kept when the reply `ts` is newer.
- [ ] T029 [P] [US2] Write failing test in `tests/integration/test_adapter_catchup.py`:
  - A missed mention gets one reply after start (SC-002).
  - A second restart gives no new reply (FR-005).
  - A new mention in a thread whose parent is older than `last_seen_ts` gets one reply (G1).
  - Crash after enqueue and before the reply: the restart answers the mention once (U1).
  - `last_seen_ts` moves forward only after a reply is posted. The live path saves it after each reply (U2).
  - `conversations.history` and `conversations.replies` read more than 100 messages with the cursor (U3).
  - `conversations.history` is called with `oldest = last_seen_ts - 7 days`.
  - An error in one channel does not stop the other channels.
  - First start sets `last_seen_ts` to the start time and answers no old history.
  - A missed mention from a non-owner runs with the empty tool set (FR-016).
  - A mention while the link is down, then `FakeTransport.reconnect()`: one reply after the reconnect, and a second `reconnect()` gives no new reply (FR-004, E1).
  - `catch_up()` runs on the worker queue and at most one `catch_up` job waits in the queue.

### Implementation for User Story 2

- [ ] T030 [P] [US2] Implement `parents_to_scan` and `pick_missed` in `src/pipe/core/catchup.py` (T028)
- [ ] T031 [US2] Add `users.conversations`, `conversations.history`, `conversations.replies`, and `on_reconnect(callback)` to `src/pipe/transport_slack.py` (T029; same file as T025):
  - Use cursor pagination for `history` and `replies`.
  - `history` takes `oldest`. The caller passes `last_seen_ts - 7 days`.
  - `replies` takes `oldest = last_seen_ts`.
  - `on_reconnect` registers a listener on the Socket Mode client (research.md A7). The listener code sits in `src/pipe/transport_slack_events.py` (T055). The exact `slack_bolt` and `slack_sdk` names are checked in T051.
- [ ] T032 [US2] Implement `catch_up()` in `src/pipe/adapter.py` (T029; depends on T030, T031):
  - One idempotent pass at start and after each Socket Mode reconnect. Wire it with `Transport.on_reconnect(callback)`: the callback puts a `catch_up` job on the worker queue (at most one waiting job). Error isolation per channel.
  - Read history from `last_seen_ts - 7 days`. Select parents with `parents_to_scan`. Call `replies(oldest=last_seen_ts)` for each. Filter mentions by `ts > last_seen_ts`.
  - Share the mention-key and in-flight sets with the live path. `handled` = `mention_keys` plus `in_flight`.
  - Route each missed mention through `should_handle`, like the live path. A missed "who works on what?" gets the `status_query` branch (T043 adds the branch; before T043 it routes to `reply`).
  - Persist the `event_id` and the mention key only after the reply or the failure message is posted.
  - Save `last_seen_ts` after each reply.

**Checkpoint**: User Stories 1 and 2 work.

---

## Phase 5: User Story 3 - Publish session status to `#pipe-status` (Priority: P2)

**Goal**: One Claude Code session gives one message in `#pipe-status`. The hooks `SessionStart`, `Stop`, and `SessionEnd` update it in place. Each update writes `updated_at`. The hook does nothing inside the adapter's `claude -p` child.

**Independent Test**: Run `pytest tests/unit/test_status.py tests/integration/test_hook.py`. Then do the quickstart scenario "3".

### Tests for User Story 3 (write first, they MUST fail)

- [ ] T033 [P] [US3] Write failing test for `next_status`, `render`, and the payload builder in `tests/unit/test_status.py` (FR-010; data-model.md SessionStatus):
  - `(none) --SessionStart--> started`.
  - `started|idle --Stop--> idle`.
  - `started|idle --SessionEnd--> stopped`.
  - `(none) --Stop--> idle`.
  - `(none) --SessionEnd--> stopped`.
  - `stopped --SessionStart--> started` (same `session_id`).
  - `updated_at` is an integer in epoch seconds. It moves forward only.
  - `blocker` is always `""`.
  - `render` gives `<who> | <repo> | <branch> | <stage> | blocker: none`.
  - `stage` is one of `started`, `idle`, `stopped`.
  - The payload holds no path, token, or URL.
  - All text fields pass through `scrub` and `escape_mentions` (a `<!channel>` in `repo` or `branch` is escaped).
- [ ] T034 [P] [US3] Write failing test in `tests/integration/test_hook.py` with `FakeCallSlack` (a recording fake of the injected `call_slack(method, payload)`, T012):
  - `SessionStart`, `Stop`, `SessionEnd` for one `session_id` give exactly one `chat.postMessage`. The rest are `chat.update` of the same `ts` (SC-003, FR-009).
  - The hook calls `call_slack` once per event (G2). The default `call_slack` uses a 5 second timeout (checked with a patched `urllib.request.urlopen`).
  - Each call writes `updated_at` in the `pipe.status.v1` metadata.
  - `Stop` or `SessionEnd` with no state file posts once and saves `channel` and `ts`.
  - `repo` is the git top-level base name, else the `cwd` base name. `branch` is `""` outside git.
  - `text`, `repo`, `branch`, and `blocker` pass through `scrub`. Mention syntax is escaped.
  - A Slack error or timeout still exits 0 and writes to `~/.pipe/logs/hook.log`.
  - With `PIPE_RUNTIME` set and non-empty, the hook exits 0 at once. It makes no Slack call and writes no file (I1). With `PIPE_RUNTIME` set to an empty string, the hook runs.
  - A lock file older than 30 seconds (file mtime) is removed by the hook, and the first post goes on. A fresh lock is not removed (E6).
  - Two concurrent first calls for one `session_id` post one message (U4).
  - The hook uses `#pipe-status` until the channel ID is cached. After the first post, it writes `status_channel_id` to `state.json` (I2).
- [ ] T037a [P] [US3] Write failing test in `tests/unit/test_state_cleanup.py` for the cleanup of status files (research.md D11):
  - A `status/<session_id>.json` file with a file mtime older than 7 days is deleted.
  - A newer file is kept.
  - Lock files are not touched (the hook owns them, T034).
  - An error on one file does not stop the others.

### Implementation for User Story 3

- [ ] T035 [US3] Implement `next_status`, `render`, and the payload builder in `src/pipe/core/status.py` (T033)
- [ ] T036 [US3] Implement the hook entry in `src/pipe/hook.py` (T034; depends on T005, T007, T011, T020, T035):
  - Run with the venv Python through the launcher. Use `pyyaml` through `load_config`. Do not import `slack_bolt` or `slack_sdk`.
  - Take an injected `call_slack(method, payload)` function. The default is `call_slack` from `src/pipe/transport_slack_http.py` (`urllib.request`, 5 second timeout). The hook is not core. It imports no `Transport` implementation that uses `slack_sdk`.
  - If `PIPE_RUNTIME` is set and non-empty, exit 0 at once.
  - Read stdin JSON (`session_id`, `cwd`). The event argument wins over `hook_event_name` (A1).
  - Use a lock file `~/.pipe/status/<session_id>.lock` with `O_EXCL` for the first post. A concurrent call waits for the state file, then does `chat.update`.
  - Call `chat.postMessage` or `chat.update` with `metadata` through `call_slack`.
  - The hook owns lock cleanup: remove the lock after the first post, and remove a lock older than 30 seconds (file mtime) before it creates one.
  - Use `#pipe-status` until `status_channel_id` is cached in `state.json`. Cache it after the first post.
  - Scrub `text`, `repo`, `branch`, and `blocker`. Never fail.
- [ ] T037 [US3] Wire `pipe status-hook <SessionStart|Stop|SessionEnd>` in `src/pipe/cli.py`. Exit code is always 0 (contracts/cli.md; depends on T036)
- [ ] T038 [US3] Delete `~/.pipe/status/<session_id>.json` files with a file mtime older than 7 days at adapter start (the adapter does not touch lock files; the hook does, T036), in `src/pipe/state.py` and `src/pipe/adapter.py` (T037a; research.md D11; depends on T007, T032)

**Checkpoint**: User Stories 1 to 3 work.

---

## Phase 6: User Story 4 - Ask "who works on what?" (Priority: P3)

**Goal**: A mention with "who works on what?" gets one line per session that was updated in the last 24 hours. The filter uses `updated_at` from the metadata, not the message `ts`. The adapter reads only bot messages and treats the data as display data.

**Independent Test**: Run `pytest tests/unit/test_status_query.py tests/integration/test_adapter_status_query.py`. Then do the quickstart scenario "4".

### Tests for User Story 4 (write first, they MUST fail)

- [ ] T039 [P] [US4] Write failing test in `tests/unit/test_status_query.py` (FR-011, SC-005):
  - `is_status_query` removes the `<@bot_user_id>` mention first. Then it matches the case-insensitive substring `who works on what` (for example `<@B> Who works on what?` and `<@B> tell me who works on what today`). It does not match other text.
  - `parse_status_messages` keeps only messages with `bot_id` set and `event_type == "pipe.status.v1"`.
  - `parse_status_messages` ignores a message without `bot_id` (a non-bot poster), even with valid metadata (C1).
  - `parse_status_messages` ignores a payload with a wrong field type or a `stage` outside `started | idle | stopped`.
  - `recent(statuses, now)` keeps a status with `updated_at` in the last 24 hours.
  - `recent` drops an older status.
  - `recent` keeps a status with an old message `ts` and a new `updated_at`.
  - `render_summary` gives one line `who | repo | branch | stage | blocker` per session.
  - An empty list gives "No sessions in the last 24 hours."
  - The `render_summary` output passes through `scrub`.
  - Mention syntax (`<!channel>`, `<!here>`, `<@U…>`) in any field is escaped.
- [ ] T040 [P] [US4] Write failing test in `tests/integration/test_adapter_status_query.py` with `FakeTransport`:
  - A status query reads `conversations.history` of `#pipe-status` with `oldest` = now minus 7 days and `include_all_metadata=true`.
  - It reads more than 100 messages with the cursor (U3).
  - The reply lists the sessions updated in the last 24 hours and none older (SC-005).
  - A status message from a non-bot poster is ignored (C1).
  - A token-like string and `<!channel>` in a metadata field do not appear unescaped in the reply (G3).
  - A "who works on what?" mention that `catch_up()` finds gets the status reply, not a runtime call (E12).
  - `FakeRuntime` is not called.
  - A non-owner sender gets the answer too.
  - The `#pipe-status` channel ID is cached in `state.json`.
- [ ] T041a [US4] Write failing test in `tests/unit/test_router.py` (same file as T015): `should_handle` returns `Decision(action="status_query")` when `is_status_query(text)` is true. It returns `reply` for other text. It still ignores bot senders and handled mentions (I5)

### Implementation for User Story 4

- [ ] T041 [US4] Add `is_status_query`, `parse_status_messages`, `recent`, and `render_summary` to `src/pipe/core/status.py` (T039; same file as T035)
- [ ] T042 [US4] Make `should_handle` return `Decision(action="status_query")` when `is_status_query(text)` is true, in `src/pipe/core/router.py` (T041a; depends on T041)
- [ ] T043 [US4] Add the `status_query` branch and the `#pipe-status` lookup in `src/pipe/adapter.py`, and `include_all_metadata` and `bot_id` support in `src/pipe/transport_slack.py` (T040; depends on T042, T025, T032):
  - Use `Transport.find_channel` (T025) to find `#pipe-status`. The core code gets `Message` objects with `sender_is_bot` (no Slack field). Cache the ID in `state.json`.
  - Make `catch_up()` (T032) use the same `status_query` branch.
  - Read history with cursor pagination.
  - Use `parse_status_messages`, `recent`, and `render_summary`. Pass the summary through `scrub`.

**Checkpoint**: User Stories 1 to 4 work.

---

## Phase 7: User Story 5 - Check the installation with `pipe doctor` (Priority: P3)

**Goal**: `pipe doctor` runs five checks and prints one line per check. All checks run after a failure.

**Independent Test**: Run `pytest tests/unit/test_doctor.py tests/unit/test_launchd.py`. Then do the quickstart scenario "5".

### Tests for User Story 5 (write first, they MUST fail)

- [ ] T044 [P] [US5] Write failing test in `tests/unit/test_doctor.py` with `FakeKeychain` and `FakeTransport` (FR-013, contracts/cli.md):
  - Five `PASS` lines on a good setup.
  - A missing Keychain item gives `FAIL token` with the fix command. The other checks still run.
  - `slack` is a `FAIL` (not a crash) when `token` failed.
  - An empty `owner` gives `FAIL owner` (U6).
  - Exit code is 0 or 1.
  - No output contains a token value.
- [ ] T045 [P] [US5] Write failing test in `tests/unit/test_launchd.py` (research.md D2, D3):
  - The plist has label `com.pipe-ai.adapter`.
  - It has `RunAtLoad` true, `KeepAlive` true, and `ThrottleInterval` 10.
  - It has the log path `~/.pipe/logs/adapter.log`.
  - It points to the launcher.
  - `plist_is_current` detects a changed target.

### Implementation for User Story 5

- [ ] T046 [P] [US5] Implement the five checks in `src/pipe/doctor.py` (the `slack` check uses `Transport.find_channel` from T025): `token`, `slack`, `claude` (`shutil.which("claude")`), `launchd`, `owner` (T044)
- [ ] T047 [P] [US5] Implement the launcher, the plist, and `launchctl bootstrap` and `bootout` with `gui/<uid>` in `src/pipe/launchd.py` (T045)
- [ ] T048 [US5] Wire `pipe doctor` and `pipe schedule --install` / `--remove` in `src/pipe/cli.py` (depends on T046, T047)

**Checkpoint**: All five user stories work.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T049 Run `pytest tests/unit tests/integration` and fix failures (quickstart section 1)
- [ ] T050 [P] Check that no file under `src/`, `tests/`, and `~/.pipe/` holds a plain token (FR-007, SC-007)
- [ ] T051 Check assumptions A1, A2, A7, and A8 against a real `claude` run (research.md "Cannot verify"). Do this task before the manual scenarios of T052:
  - First, run a real `claude -p --tools ""` with the prompt "read this file: <path>". Confirm that no tool runs and the file is not read (E2).
  - Run the built owner command with the prompt "read ~/.ssh/config". Confirm that the read is refused (FR-018; E17). If it is not refused, add the `--disallowedTools` deny rules of research.md D8 and test again.
  - Ask the owner run to run `git push`. Confirm that the call is denied by the `--disallowedTools` default `Bash(git push:*)` (FR-019). Check the rule syntax.
  - Check the path rule syntax (`Read(//<root>/**)`) with a read inside a root (allowed) and in a second `--add-dir` root (allowed) (A8).
  - Check how `slack_bolt` Socket Mode exposes a reconnect listener, and fix `on_reconnect` in `src/pipe/transport_slack_events.py` if the names differ (A7).
  - Check the hook stdin keys.
  - Check the `--output-format json --json-schema` envelope.
  - Check that a real `claude -p` run from the adapter posts no status message (`PIPE_RUNTIME=1` works with the owner's hooks; the guard is "set and non-empty").
  - Correct `src/pipe/hook.py` and `src/pipe/core/contract.py` if they differ.
- [ ] T052 Run the manual scenarios of `quickstart.md` section 3 and section 4 on a real Slack workspace (including the hooks `SessionStart`, `Stop`, `SessionEnd`):
  - Check the scope `metadata.message:read`: the status query reads the metadata of bot messages in `#pipe-status` (A3).
  - Time each status change. It must be visible within 30 seconds (SC-004).
  - Cut the network, mention the bot, restore the network: one reply (quickstart "2 (reconnect)").
  - The owner asks for `~/.ssh/config`: the reply says it cannot read it (quickstart "1 (owner path limit)").
  - Time the diagnosis of a setup problem with `pipe doctor`. It must take under 2 minutes (SC-006, manual).

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependency.
- Foundational (Phase 2): needs Phase 1. It blocks all user stories.
- US1 (Phase 3): needs Phase 2 (T053 to T056 included). No dependency on other stories.
- US2 (Phase 4): needs Phase 2 and T025, T026 of US1 (shares `adapter.py` and `transport_slack.py`). T032 wires the reconnect handler through `Transport.on_reconnect` (T010, T031).
- US3 (Phase 5): needs Phase 2. T036 needs T005, T007, T011, T020, T035 (config, state, Keychain, scrub, status). T038 needs T032 (it edits `adapter.py` after the catch-up code) and T037a.
- US4 (Phase 6): needs T035 (US3) and T026 (US1). T041a (test) comes before T042. T043 needs T031 (pagination in `transport_slack.py`), T025 (`find_channel`), and T032 (`catch_up()` uses the same status branch).
- US5 (Phase 7): needs Phase 2. The tests T044 and T045 and the launchd code T047 have no other dependency. The `slack` check (T046) and its real run need T025 (`Transport.find_channel`, US1). So US5 is not fully independent of US1.
- Polish (Phase 8): needs all stories.

### Within Each User Story

- Test tasks come first and MUST fail before the implementation task.
- Pure functions in `src/pipe/core/` before the I/O code that calls them.
- Tasks that edit the same file are not marked [P].
- Test-first pairs: T057 before T058 and T023. T059 before T060. T061 before T062. T063 before T064. T037a before T038. T041a before T042. T040 before T043. T029 before T032. T053 before T054. T056 before T025 and T031. The IDs T053 to T056 were added after the first numbering. They sit in Phase 2, in file order.

### Parallel Opportunities

- Phase 2: T004, T006, T008 together; then T010, T011.
- US1 tests T014 to T019 together; then T020 to T023 together.
- US5 can run in parallel with US2 to US4 with another developer, after T025 is done.

---

## Parallel Example: User Story 1

```text
# Launch all pure-function tests together:
Task: "Write failing test for scrub in tests/unit/test_scrub.py"
Task: "Write failing test for should_handle in tests/unit/test_router.py"
Task: "Write failing test for tools_for(sender, owner, owner_tools, deny_rules) in tests/unit/test_runtime_claude_tools.py"

# Then the pure functions together:
Task: "Implement scrub in src/pipe/core/scrub.py"
Task: "Implement tools_for in src/pipe/runtime_claude_tools.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Stop and validate: tests pass, then quickstart scenarios "1".
4. Demo.

### Incremental Delivery

1. Add US2 (catch-up). Validate.
2. Add US3 (status hooks). Validate.
3. Add US4 (status query). Validate.
4. Add US5 (doctor and launchd). Validate.

### Traceability of the approved changes

Earlier decisions (Q1 to Q5, resolved 2026-11-25):

- F-Q5 (non-owner has no tools): T017, T018, T019, T023, T024, T029.
- F-Q1 (`owner` config key): T004, T005, T023.
- F-Q2 (`SessionEnd` hook): T033, T034, T036, T037, T052.
- F-Q3 (no blocker command): T033 (blocker always `""`).
- F-Q4 (`updated_at` in metadata): T033, T034, T039, T040, T041.

Approved `/speckit-analyze` findings (labels start with `F-`, so they do not clash with the research assumptions A1 to A8):

- F-C1 (status metadata from bot posters only): T039, T040, T041, T043.
- F-G1 (catch-up in old threads): T028, T029, T030, T031, T032.
- F-U1 (in-flight set, persist after reply): T015, T019, T026, T029, T032.
- F-I1 (`PIPE_RUNTIME=1`): T018, T024, T034, T036, T051.
- F-G3 (scrub and escape): T014, T020, T033, T034, T039, T040.
- F-C5 (read-only owner tools): T017, T023.
- F-C2 (`max_budget_usd`): T004, T005, T018, T024.
- F-U2 (`last_seen_ts` in the live path): T019, T026, T029.
- F-U3 (cursor pagination): T012, T029, T031, T040, T043.
- F-U4 (session lock): T034, T036.
- F-U5 (`runtime.claude.owner_tools`): T004, T005, T017, T023.
- FR coverage by the user story tests (no `F-` label): FR-001 and FR-003 (T015, T016, T019), FR-008 (T033, T034, T036), FR-017 (T033). FR-015 is a negative rule: no task adds a database, a web UI, or a hosted service.
- F-U6 (`runtime.claude.deny_rules` and FR-019, added 2026-11-26): T004, T005, T017, T018, T023, T024.
- F-I2 (hook config and channel ID cache): T034, T036.
- F-I3 (US3 scenario 2): spec.md only.
- F-I4 (assumptions note): spec.md only.
- F-G2 (hook timing, SC-004): T034, T052.
- F-A1 (one match rule): T039, T042.
- F-C3 (constitution 1.0.1): `.specify/memory/constitution.md`, plan.md. No task.
- F-C4 (short task lines): all tasks of this file.
- F-U6 (first start, `owner` warning, doctor check): T004, T005, T044, T046.
- F-I5 (new test tasks): T037a, T041a.
- F-A2 (SC-006 manual): T052.
- F-D1 (cross-references in spec): spec.md only.

Approved changes of analyze pass 2:

- F-E1 (catch-up on each reconnect): T012, T010, T029, T031, T032, T051.
- F-E2 (real `--tools ""` run): T051.
- F-E3 (stub script in T018): T001, T018, T024.
- F-E4 (injected `call_slack`): T012, T034, T036.
- F-E5 (`find_channel` in T025; US5 dependency): T025, T043, T046.
- F-E6 (lock cleanup by the hook; status files by the adapter): T034, T036, T037a, T038.
- F-E7 (`F-` labels): this section.
- F-E8 (T037a, T041a moved to test blocks): Phases 5 and 6.
- F-E9 (`tools_for` signature): research.md D8, parallel example.
- F-E10 (`PIPE_RUNTIME` set and non-empty): T034, T036, T051.
- F-E11 (`max_budget_usd` assumption): spec.md, plan.md.
- F-E12 (catch-up routing and `handled`): T028, T032, T040, T043.
- F-E13 (crash stays `started` or `idle`): spec.md.
- F-E14 (`metadata.message:read`): research.md D5 and A3, quickstart.md, T052.
- F-E15 (`--restricted` rule; cli.md): T017, T018, T024, contracts.
- F-E16 (five doctor checks): spec.md.
- F-E17 (owner path limit, accepted risk): FR-018, T018, T024, T051, plan.md Complexity Tracking.

Added 2026-11-26 (owner decision: flexible core, Transport port; constitution 1.2.0):

- F-T1 (Transport port, neutral identities, Slack adapter modules `transport_slack_*`): FR-020, FR-021, T010, T012, T025, T026, T027, T031, T053, T054, T055, T056.
- F-T2 (`ToolPolicy` moves out of the core into the `claude` adapter; `RuntimeInput.requester_is_owner`; `is_owner`): FR-022, T009, T015, T017, T023, T024, T026.
- F-T3 (`RuntimeOutput.data`; other runtime adapters): FR-023, T008, T009.

Added 2026-11-26 (second batch of owner decisions, constitution 1.3.0):

- F-N1 (`deny_rules` is a union with the default `Bash(git push:*)`): FR-019, SC-010, T004, T005, T017, T023, T057, T058.
- SC-008 (import boundary): spec 003 T071 (it globs every core module). SC-009 (core rules run with `FakeTransport`): T056 and every pure-function test task.
- F-N2 (`Transport.upload_file`, scope `files:write`): FR-024, SC-011, T059, T060.
- F-N3 (`pipe flows` command): FR-025, SC-012, T061, T062.
- F-N4 (runtime status `waiting`, `reason`, `proposal`): FR-026, T008, T063, T064.

---

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Verify that each test fails before you write the implementation.
- Do not commit from these tasks without an explicit owner request.
