# Implementation Plan: Adapter Core and Status

**Branch**: `001-adapter-core-status` | **Date**: 2026-11-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-adapter-core-status/spec.md`

## Summary

`pipe-adapter` is one Python process per owner. launchd starts it. The core talks to the chat system only through the `Transport` port. The first adapter, `transport_slack_*`, listens to Slack with Socket Mode. On a mention, it builds a thread context, calls the runtime (`claude -p`) through one contract, removes token-like strings, and replies in the thread. At start and after each Socket Mode reconnect, it reads `conversations.history` (from the last seen `ts` minus 7 days) and `conversations.replies` for threads with new replies, and answers missed mentions. A separate hook script (events `SessionStart`, `Stop`, `SessionEnd`; it does nothing when `PIPE_RUNTIME` is set and non-empty) posts session status to `#pipe-status` and updates the same message with `chat.update`. Any online agent answers "who works on what?" from the `#pipe-status` messages of the last 24 hours. `pipe doctor` checks the setup. Details: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.15.2 is the version on this machine (`python3 --version`). The floor is Python 3.15. Code uses no 3.15-only feature, so a lower floor is possible later (see research.md D1).

**Primary Dependencies**: `slack_bolt` (Socket Mode, used only by the `transport_slack_*` modules), `pyyaml`. Test-only: `pytest`. No other runtime dependency. The hook script takes an injected `call_slack(method, payload)` function (default: `urllib`). The hook script runs with the venv Python through the launcher, like the adapter. It may import `pyyaml` and `pipe.*` modules. It does not import `slack_bolt` or `slack_sdk`. It calls Slack with `urllib`.

**Storage**: Files under `~/.pipe/` (JSON, atomic write). No database.

**Testing**: `pytest`. Pure functions have unit tests first. Unit test cases for `tools_for` (`src/pipe/runtime_claude_tools.py`, `claude` adapter): (a) `requester_is_owner` true gives the `runtime.claude.owner_tools` list (default `Read`, `Grep`, `Glob`) `disallowed` = `effective_deny_rules(runtime.claude.deny_rules)` (always has `Bash(git push:*)`); (b) `requester_is_owner` false gives an empty tool set (`tools=[]`, `allowed=[]`, `disallowed=[]`), so the command has `--tools ""`; (b2) `restricted=True` in both cases (`--restricted` is always passed, see research.md D8). The core function `is_owner(sender_id, owner)` (`core/router.py`) gives false when `owner` is missing or empty, so every sender gets the empty tool set. Integration test: a non-owner asks to read a local file; the fake runtime receives an empty tool set and no file is read (FR-016). Build-command unit test: the owner command has `--restricted`, `--permission-mode dontAsk`, and path allow rules for each `runtime.claude.repo_roots` entry and `--disallowedTools` with the `deny_rules` entries. Slack and the runtime sit behind two interfaces (`Transport`, `RuntimePort`) with fakes in tests.

**Target Platform**: macOS laptop. launchd runs the adapter. The Keychain holds the Slack tokens.

**Project Type**: CLI and background process (`pipe`, `pipe-status-hook`).

**Performance Goals**: A status change is visible in 30 seconds (SC-004). One mention gives one reply (SC-001).

**Constraints**: No server, no database, no web UI. One runtime call at a time per adapter. Each runtime call has a timeout (`step_timeout_min`, default 30). An optional spend limit (`max_budget_usd`, default unset) goes to `claude -p` as `--max-budget-usd`. The owner's run reads only inside `runtime.claude.repo_roots` (`--restricted`, `--permission-mode dontAsk`, path allow rules; research.md D8). No plain token in any file.

**Scale/Scope**: 3 to 6 developers, one adapter each. A few mentions per hour. Less than 100 status messages per day.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.3.0.

| Principle | Pre-research | Post-design | Note |
|---|---|---|---|
| I. No Server in the MVP | PASS | PASS | Files, Slack, launchd only. |
| II. The Owner Controls the Agent | PASS | PASS | The adapter runs locally. The owner sets the `owner` config key. The no-tools policy for non-owners (design brief §8, D8) is the 001 control for "who may send". The owner can widen the owner tool list with `runtime.claude.owner_tools`. The owner's own run is limited to read-only tools inside `runtime.claude.repo_roots` (D8); see the Complexity Tracking row. |
| III. Discovered Is Not Exposed | PASS (not in scope) | PASS | No discovery in 001. Non-owner senders get no owner credentials and no file access, because the runtime has no tools (D8). |
| IV. Every Change Goes Through an MR | PASS (not in scope) | PASS | 001 has no delegation. The runtime has no push instruction. Non-owner senders have no tools, so they cannot write or read. |
| V. Thread Content Is Untrusted Input | PASS with a justified deviation | PASS with a justified deviation | 001 reads no `metadata` as a command. The status query reads `pipe.status.v1` metadata from posters that have no agent card. See the Complexity Tracking row. The thread is wrapped as untrusted text in the prompt (D7). |
| VI. Runtime-Agnostic Contract | PASS | PASS | `RuntimePort` follows brief §5.1. `ToolPolicy` is a `claude` adapter type, not a core type. The runtime gets no `hop`, trust, or Slack data. See [contracts/runtime-contract.md](contracts/runtime-contract.md). The keys of the `claude` adapter (`owner_tools`, `repo_roots`, `deny_rules`) sit in the config section `runtime.claude` (brief §5.4). The core does not read it. |
| VII. Business Rules Are Pure Functions | PASS | PASS | Router (`should_handle`), dedupe, scrub, catch-up selection, tool selection, status render and filter (by `updated_at`) are pure. Tests come first. |
| VIII. Reuse Before Build | PASS | PASS | Copies tick, launcher, doctor, launchd plist, `claude -p` patterns. See research.md D2. |
| IX. Small Dependencies | PASS | PASS | Only `slack_bolt`, `pyyaml`. `pytest` is test-only. |
| X. STE for All Written Artifacts | PASS | PASS | All artifacts use STE. |
| XI. Core Is Capability-, Runtime-, and Transport-Agnostic | PASS | PASS | `core/` imports no `transport_slack*` module, no `slack_bolt`, and no `runtime_claude*` module. The core uses `Transport`, `RuntimePort`, and the neutral identities `sender_id`, `sender_is_bot`, `card_owner_id` ([contracts/transport.md](contracts/transport.md)). `ToolPolicy` and `tools_for` sit in `runtime_claude_tools.py`. The import-boundary test is task T071 of spec 003. |

Note: the optional `max_budget_usd` key limits the spend of one runtime call. It is a cost limit, not an owner-control rule.

Technology and Security Constraints: Keychain for tokens (PASS, D4). Scrub before post (PASS, D6). Tool lists for foreign tasks (PASS, D8). The constitution PATCH 1.0.1 (2026-11-25) changes the foreign-task rule to: "A task from a non-owner runs with an allowed-tools list for its kind, or with no tools. It never gets `owner-only` tools." The empty tool set of D8 meets this rule. `hop` limit: 001 does not create `hop`; the field is reserved in the runtime contract (PASS, not in scope). Cards: not in scope.

Resolved 2026-11-25: Q1 (config key `owner` accepted), Q2 (`SessionEnd` hook added), Q3 (no blocker command in 001), Q4 (`updated_at` in metadata), Q5 (non-owner runs with no tools). No open question remains.

**Result**: PASS. One justified deviation (principle V) and one accepted residual risk (principles V and II, owner run). See Complexity Tracking.

## Design decisions

The owner confirmed these decisions on 2026-11-26 (second batch). Each decision is in force. The tasks follow them.

- **N1. `deny_rules` is a union.** `Bash(git push:*)` is ALWAYS denied in an owner run. The owner list only adds rules. FR-019, SC-010. Tasks: T004, T005, T017, T057, T058, T023.
- **N2. `Transport.upload_file`.** FR-024, SC-011. Slack scope `files:write`. Tasks: T059, T060.
- **N3. Runtime `waiting` and `proposal`.** FR-026. Tasks: T008, T063, T064.
- **N4. `pipe flows`.** FR-025, SC-012. Tasks: T061, T062.

## Project Structure

### Documentation (this feature)

```text
specs/001-adapter-core-status/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── runtime-contract.md
│   ├── status-hook.md
│   └── cli.md
└── tasks.md             # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

```text
pyproject.toml           # created at implement time; deps: slack_bolt, pyyaml; test: pytest
src/pipe/
├── core/                # PURE functions only. No I/O, no Slack, no subprocess.
│   ├── router.py        # should_handle(event, self_ids, seen) -> Decision ; is_owner(sender_id, owner) -> bool (false when owner is empty)
│   ├── dedupe.py        # remember(seen, keys) -> seen (bounded)
│   ├── catchup.py       # parents_to_scan(history, last_ts) -> list ; pick_missed(messages, last_ts, self_user_id, handled) -> list
│   ├── scrub.py         # scrub(text) -> text   (escape_mentions comes from the Transport Formatter, not from core)
│   ├── status.py        # next_status(prev, event) ; render(status) ; parse_status_messages(msgs) (sender_is_bot only) ; is_status_query(text) ; recent(statuses, now) by metadata updated_at ; render_summary
│   └── contract.py      # dataclasses: RuntimeInput, RuntimeOutput (with optional data), neutral Message, Identity, Button, MentionEvent; parse_output(stdout). No ToolPolicy here
├── ports.py             # Transport, RuntimePort, Formatter (Protocol)
├── transport_slack.py        # Slack adapter: Transport over slack_sdk WebClient (I/O)
├── transport_slack_events.py # Slack adapter: slack_bolt Socket Mode handlers -> neutral events; reconnect listener (I/O)
├── transport_slack_map.py    # Slack adapter, pure: Slack message -> Message (sender_id, sender_is_bot), buttons -> Block Kit, mention, escape_mentions
├── transport_slack_http.py   # Slack adapter: call_slack(method, payload) over urllib, for the status hook only
├── runtime_claude_tools.py # `claude` adapter, pure: ToolPolicy dataclass and tools_for(requester_is_owner, owner_tools, deny_rules) -> ToolPolicy and effective_deny_rules(deny_rules) (owner: runtime.claude.owner_tools and the effective deny list; other: empty tool set; restricted=True for all). Not a core module
├── runtime_claude.py    # RuntimePort over `claude -p`; build_cmd adds --restricted, --permission-mode dontAsk, --add-dir and path allow rules from runtime.claude.repo_roots
├── keychain.py          # `security` CLI wrapper
├── state.py             # ~/.pipe files, atomic write
├── config.py            # load ~/.pipe/config.yaml (section runtime.claude: owner_tools, repo_roots, deny_rules)
├── adapter.py           # run loop: Transport.on_event handler, catch-up (at start and on reconnect), worker queue. Imports no Slack module
├── hook.py              # pipe-status-hook entry (venv Python; no slack_bolt; call_slack(method, payload) injected, default from transport_slack_http.py)
├── launchd.py           # plist, launcher, schedule --install/--remove
├── doctor.py            # five checks
└── cli.py               # `pipe run | doctor | schedule | status-hook`

tests/
├── unit/                # one file per core module; written before the code
├── fakes.py             # FakeTransport (in-memory Transport; the former FakeSlack), FakeCallSlack (hook), FakeRuntime, FakeKeychain
└── integration/         # adapter.py with fakes: mention, duplicate, restart, runtime failure, non-owner file request
```

**Structure Decision**: Single project. `core/` holds all business rules as pure functions. Everything with I/O sits outside `core/` and behind a port.

## Complexity Tracking

| Principle | Deviation | Why needed | Simpler alternative rejected because |
|---|---|---|---|
| V. Thread Content Is Untrusted Input | 001 reads `pipe.status.v1` metadata from `#pipe-status` as display data only, because agent cards start in spec 002. Mitigation: accept only messages with `bot_id`; escape mentions; scrub; never use the data as a command. | The status query (US4) needs the status messages. Agent cards do not exist yet, so the adapter cannot check "a bot that has an agent card". | Ignore all metadata: US4 cannot work. Wait for spec 002: US4 moves out of 001 and the status feature gives no shared view. |
| II. The Owner Controls the Agent; V. Thread Content Is Untrusted Input | The owner's own run reads text from other people in a thread (prompt injection). 001 accepts this MVP risk. The limit: read-only tools (`Read`, `Grep`, `Glob`) and only inside `runtime.claude.repo_roots` (D8: `--restricted`, `--permission-mode dontAsk`, path allow rules). A secret inside a repo root can still reach a reply; `scrub` removes only token-like strings. | The owner needs read access to answer thread tasks. | No tools for the owner: the agent cannot help with code. Ask the owner to approve each run: no unattended agent. |
