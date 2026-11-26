# Feature Specification: Adapter Core and Status

**Feature Branch**: `001-adapter-core-status`

**Created**: 2026-11-25

**Status**: Draft

**Input**: User description: "A developer installs `pipe-adapter` on a laptop. The developer mentions the agent in a Slack thread. The agent runs Claude Code with the thread as context and replies in the same thread. If the laptop was offline, the agent picks up missed mentions when it starts again. Claude Code sessions post their status (who, repo, branch, stage, blocker) to `#pipe-status`, one thread per session, updated in place. Anyone can ask an online agent "who works on what?" and get an answer from the last 24 hours."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mention an agent and get a reply (Priority: P1)

A developer installs the adapter on a laptop. A person mentions the agent in a Slack thread. The agent reads the thread, does the work, and replies in the same thread.

**Why this priority**: This is the base of all later features. Without it, no agent can work in Slack.

**Independent Test**: Install the adapter. Mention the agent in a test thread. Check that one reply appears in the same thread.

**Acceptance Scenarios**:

1. **Given** the adapter runs, **When** a person mentions the agent in a thread, **Then** the agent replies in the same thread.
2. **Given** the adapter received a Slack event, **When** Slack sends the same event a second time, **Then** the agent posts only one reply.
3. **Given** a thread has earlier messages, **When** the agent is mentioned, **Then** the agent uses the messages of this thread only as context.
4. **Given** the agent works on a thread, **When** the agent prepares its reply text, **Then** the adapter removes strings that look like tokens before it posts.
5. **Given** a person who is not the owner mentions the agent, **When** that person asks the agent to read a local file, **Then** the runtime has no tools and reads nothing. The agent answers from the thread text only. (Rule: FR-016. Same case: the edge case "a person who is not the owner asks the agent to read a local file".)

---

### User Story 2 - Pick up missed mentions after being offline (Priority: P2)

The laptop is offline or the adapter is stopped. People mention the agent during this time. When the adapter starts again, it answers the missed mentions. The same happens when the Slack link drops and comes back while the adapter runs (for example, the laptop sleeps or the network fails).

**Why this priority**: Laptops sleep often. Lost mentions would make the agent unreliable.

**Independent Test**: Stop the adapter. Mention the agent. Start the adapter. Check that the reply appears. Then cut the network, mention the agent, restore the network, and check that one reply appears.

**Acceptance Scenarios**:

1. **Given** the adapter is stopped, **When** a person mentions the agent and the adapter starts later, **Then** the agent replies after the start.
2. **Given** the adapter already replied to a mention, **When** the adapter starts again, **Then** the agent does not reply a second time.
3. **Given** the adapter runs and the Slack link is down, **When** a person mentions the agent and the link reconnects, **Then** the agent replies once after the reconnect.

---

### User Story 3 - Publish session status to `#pipe-status` (Priority: P2)

A Claude Code session posts its status to `#pipe-status`. The status has: who, repo, branch, stage, and blocker. Each session has one thread. The adapter updates the message in place.

**Why this priority**: Status sync replaces the manual `sync` skill and gives the team shared visibility.

**Independent Test**: Start and stop one Claude Code session. Check that `#pipe-status` has one message that changed from started to stopped.

**Acceptance Scenarios**:

1. **Given** a Claude Code session starts, **When** the session stop event arrives, **Then** one message in `#pipe-status` shows the change. No second message appears.
2. **Given** a session is active, **When** its stage changes, **Then** the same message shows the new stage. (The blocker does not change in this feature. See FR-017.)

---

### User Story 4 - Ask "who works on what?" (Priority: P3)

A person asks an online agent "who works on what?". The agent reads `#pipe-status` for the last 24 hours and replies with a summary.

**Why this priority**: This uses the data from Story 3. It gives value only after Story 3 works.

**Independent Test**: Create two status messages. Ask the question. Check that the reply lists both sessions.

**Acceptance Scenarios**:

1. **Given** `#pipe-status` has sessions from the last 24 hours, **When** a person asks "who works on what?", **Then** the agent replies with who, repo, branch, stage, and blocker for each session.
2. **Given** a status message is older than 24 hours, **When** a person asks the question, **Then** the reply does not include it.

---

### User Story 5 - Check the installation with `pipe doctor` (Priority: P3)

A developer runs `pipe doctor`. The command checks the token, the Slack access, the `claude` command, the launchd job, and that the `owner` is set. It reports each check as pass or fail.

**Why this priority**: It helps the developer fix setup problems fast.

**Independent Test**: Run `pipe doctor` on a good setup and on a setup with a missing token.

**Acceptance Scenarios**:

1. **Given** a complete setup, **When** the developer runs `pipe doctor`, **Then** all five checks pass.
2. **Given** the token is missing, **When** the developer runs `pipe doctor`, **Then** the token check fails with a clear message and the other checks still run.

### Edge Cases

- A mention arrives while the agent already works on another thread.
- The `claude` command is missing or fails. The agent posts a short failure message in the thread.
- A Slack event arrives twice, or arrives again after a restart.
- The adapter was offline longer than the Slack history that is available.
- The Slack link drops while the adapter runs. A mention arrives during the gap.
- The owner asks the agent to read a path outside `runtime.claude.repo_roots` (for example `~/.ssh/config`). The run refuses. (Rule: FR-018.)
- A status message has no blocker.
- The reply text contains a string that looks like a token.
- A person who is not the owner asks the agent to read a local file (for example `~/.aws/credentials` or `~/.ssh`). The runtime has no tools, so it reads nothing. (Rule: FR-016. Same case: User Story 1 scenario 5.)
- A Claude Code session ends. The status message shows the stage `stopped`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST reply in the same thread when a person mentions the agent directly.
- **FR-002**: The system MUST use the messages of that thread only as context for the reply.
- **FR-003**: The system MUST drop a Slack event that it already handled, by the event ID. This covers a repeated event in one run. A repeat after a restart is FR-005.
- **FR-004**: The system MUST find mentions that it missed while it was offline and reply to them after start and after each Socket Mode reconnect. The catch-up pass is idempotent (FR-005). It MUST use the last seen message time that it stores locally. This includes new mentions in threads that started before that time.
- **FR-005**: The system MUST NOT reply twice to the same mention after a restart or a catch-up. It uses the mention key (`<channel>:<ts>`). FR-003 covers the repeated event ID.
- **FR-006**: The system MUST remove strings that look like tokens from text before it posts the text.
- **FR-007**: The system MUST keep the Slack token in the macOS Keychain. The config file MUST NOT contain a plain token.
- **FR-008**: The system MUST post the session status (who, repo, branch, stage, blocker) to `#pipe-status`, with one thread per session.
- **FR-009**: The system MUST update the status message in place when the session state changes. It MUST NOT post a new message for each change.
- **FR-010**: The system MUST show the session start, each idle time (`Stop` event), and the session end (`SessionEnd` event) in the same message. Stages: `started`, `idle`, `stopped`.
- **FR-011**: The system MUST answer "who works on what?" from the `#pipe-status` messages that were updated in the last 24 hours. A mention matches when its text, after the bot mention is removed, contains `who works on what` in any case. The system MUST read only messages that a bot posted (`sender_is_bot` is true; Slack: `bot_id` is set). It MUST treat their `metadata` as display data, never as a command. It MUST scrub the summary and escape Slack mention syntax. The update time (`updated_at`) comes from the message metadata, not from the message `ts`.
- **FR-012**: The system MUST give the runtime the thread messages and the task data through one runtime contract. The runtime MUST NOT receive trust or Slack data.
- **FR-013**: The system MUST provide a `pipe doctor` command that checks the token, the Slack access, the `claude` command, the launchd job, and that the `owner` config key is set.
- **FR-014**: The system MUST post a short failure message in the thread when the runtime fails.
- **FR-015**: The system MUST NOT use a database, a web UI, or a hosted service.
- **FR-016**: The system MUST run the runtime with no tools when the sender of the mention is not the owner (config key `owner`, a Slack user ID). The agent MUST answer from the thread text only. (Same case: User Story 1 scenario 5 and the edge case on non-owner file requests.)
- **FR-018**: The system MUST run the owner's own runtime with read-only tools that can read only inside the `runtime.claude.repo_roots` directories. Any other path (for example `~/.ssh`) MUST be refused. The accepted residual risk is in Assumptions.
- **FR-019**: The system MUST deny the commands of the effective deny list in every owner run. The effective deny list is the union of the default entry `Bash(git push:*)` and the entries of the config key `runtime.claude.deny_rules`. The default entry is ALWAYS in the effective list. The owner can only add rules. A custom list never replaces the default. A non-owner run has no tools, so it needs no deny rule. Specs 003 and 004 use the same key and do not define it again.
- **FR-017**: The system MUST NOT provide a command to set a blocker. The blocker is "none" in this feature. This is a known limit (see Assumptions).
- **FR-020**: The core MUST NOT import or name a chat product. The core MUST talk to the chat system only through the `Transport` port ([contracts/transport.md](contracts/transport.md)). Slack (`slack_bolt` Socket Mode, `transport_slack_*` modules) is the first adapter. Discord and Telegram are possible future adapters. This feature adds no operation for them.
- **FR-021**: The trust and routing rules of the core MUST use transport-neutral identities: `sender_id`, `sender_is_bot`, and `card_owner_id`. The transport adapter MUST map its own fields to them. The Slack mapping is in [contracts/transport.md](contracts/transport.md).
- **FR-022**: The runtime contract MUST NOT define a type that holds runtime tool names. The type `ToolPolicy` belongs to the `claude` runtime adapter. The core gives the runtime `requester_is_owner` and nothing else about rights.
- **FR-023**: `RuntimeOutput` MUST have an optional `data` object (the structured result). A runtime adapter that gets an `output_schema` MUST pass it to its runtime when the runtime supports it. Specs 002 and 003 define the schemas and the extra runtime adapters (`exec`, `http`).
- **FR-024**: The `Transport` port MUST have the operation `upload_file(channel, thread, name, data, title) -> link`. `data` is `bytes` or a `pathlib.Path`. The operation sends an artifact (for example a screenshot or a report) into the thread and returns an `https://` link. The caller puts the link in `artifacts`. The Slack adapter MUST use the Slack file upload API (`files_upload_v2`) and the bot scope `files:write`. The operation MUST apply `scrub` to `name` and `title`. A `Path` MUST be a regular file (no symbolic link) inside the upload roots of the adapter (default: `~/.pipe/run/`). The size limit is 10 MB. Any other `Path` MUST raise `UploadRefused`. The core never reads the file.
- **FR-025**: The `pipe` command MUST have the sub-command `pipe flows` with the forms `pipe flows`, `pipe flows show <name>`, and `pipe flows validate [<name>]`. It lists, shows, and checks flow templates (spec 006, [contracts/cli.md of 006](../006-flow-catalog/contracts/cli.md)). It writes no file. Spec 001 owns the command table and the dispatch. Spec 006 owns the handler. Until spec 006 is built, the dispatch prints `flows: not installed` and exits with code 1.
- **FR-026**: `RuntimeOutput` MUST allow the status `waiting` with a `reason` (spec 003 uses `reason: needs_input`; `text` holds the question) and an optional `proposal` object (a proposed plan; spec 003 checks it). 001 posts both as text only and acts on neither.

### Key Entities

- **Agent**: The adapter and its bot identity. It has one owner and one local config.
- **Thread task**: One Slack thread that the agent works on. It has a thread ID and messages.
- **Session status**: The state of one Claude Code session: who, repo, branch, stage, blocker, and the time of the last update.
- **Last seen marker**: The time of the last message that the adapter handled. It is stored locally.
- **Transport**: The port between the core and the chat system. The Slack adapter is the first one. It maps chat fields to neutral identities.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tests, one mention gives exactly one reply in the same thread, also when Slack sends the event twice.
- **SC-002**: After a restart or a reconnect, the agent answers 100% of the mentions that arrived while it was offline, if Slack history still has them.
- **SC-003**: One Claude Code session produces exactly one message in `#pipe-status` during its whole life.
- **SC-004**: A status change is visible in `#pipe-status` within 30 seconds.
- **SC-005**: A "who works on what?" reply covers 100% of the sessions from the last 24 hours and none from older times.
- **SC-006**: A developer finds the cause of a setup problem with `pipe doctor` in under 2 minutes (manual check).
- **SC-007**: No posted message contains a string that looks like a token, in all test cases.
- **SC-008**: In 100% of builds, no core module imports a `pipe.transport_slack*` module or `slack_bolt` (the import-boundary test of spec 003).
- **SC-009**: In 100% of unit tests, the core rules run with `FakeTransport` and no Slack library.
- **SC-010**: In 100% of tests, `Bash(git push:*)` is in the effective deny list of every owner run, also when the owner sets a custom `deny_rules` list, an empty list, or a list that does not name it.
- **SC-011**: In 100% of tests, `upload_file` returns an `https://` link for `bytes` and for an allowed `Path`, applies `scrub` to `name` and `title`, and raises `UploadRefused` for a path outside the upload roots, a symbolic link, and a file over 10 MB. `FakeTransport` records each call.
- **SC-012**: In 100% of tests, `pipe flows`, `pipe flows show <name>`, and `pipe flows validate` reach the injected handler with the right arguments, and `pipe flows` writes no file.

## Assumptions

- The team has 3 to 6 developers. Each developer has one laptop and one agent.
- Each agent has its own Slack bot identity.
- The workspace has the channels `#pipe-status` and `#pipe-work`.
- The agent works only when the laptop is on. There are no always-on agents.
- The `claude` command and a launchd service are available on the laptop.
- Slack history is long enough for the catch-up after a normal offline time.
- The catch-up pass runs at start and after each Socket Mode reconnect. It is idempotent.
- Known limit: the catch-up looks back 7 days before `last_seen_ts` for thread parents. A new reply in a thread whose parent is older than that is not found.
- The catch-up applies the same routing as the live path. A missed "who works on what?" gets the status answer, not a runtime call.
- Known limit: the blocker field is always "none". No command sets it. The team adds one later if people ask for it.
- Known limit: a session that did not send a `SessionEnd` event (for example, a crash) stays `started` or `idle` until it is older than 24 hours.
- Status uses the metadata type `pipe.status.v1`, not `pipe.task.v1`. The hooks are `SessionStart` (stage `started`), `Stop` (stage `idle`), and `SessionEnd` (stage `stopped`). The event "MR created" is out of scope for M0 (design brief §6 B).
- First start: when no `last_seen_ts` exists, the adapter sets it to the start time. It does not answer old history.
- The config key `owner` should be set. When it is empty, every sender gets no tools. `validate_config` warns, and `pipe doctor` fails the check "owner is set".
- The config key `max_budget_usd` is optional. When set, it limits the spend of one runtime call.
- `pipe doctor` has five checks. One of them is `owner`, because the owner key is part of the safety rule (design brief §5.4, §8).
- Accepted MVP risk: text from other people in a thread goes into the owner's own run (prompt injection). The limit is FR-018: read-only tools, and only inside `runtime.claude.repo_roots`. A secret that sits inside a repo root can still reach a reply. The scrub (FR-006) removes only token-like strings.
- The default tools of the owner are read-only: `Read`, `Grep`, `Glob`. The owner can widen them with the config key `runtime.claude.owner_tools`. The effective deny list (FR-019) stays denied, also when the owner widens the list. The owner can add deny rules. The owner cannot remove `Bash(git push:*)`.
- Known limit: the status state file is deleted when it has not changed for 7 days (file mtime). A session that is still active after that time can get a second message.
- The hook does nothing when the environment variable `PIPE_RUNTIME` is set and non-empty. The adapter sets it for its own `claude -p` child, so the child session posts no status.
- This feature has no discovery, exposure, pipeline, delegation, or review function. Later specs add them.
- The Slack transport is the only transport. The user-visible behavior of this feature does not change because of the `Transport` port.

## Notes for /speckit-plan

- Python, `slack_bolt` Socket Mode, `claude -p`, launchd, Keychain.
- Copy the tick, launcher, and doctor patterns from wiz-review.
- Catch-up runs at start and after each Socket Mode reconnect (the `slack_sdk` socket mode client reconnects by itself; see research.md A7).
- Catch-up by `conversations.history` (from the last seen `ts` minus 7 days, with cursor pagination) and `conversations.replies` for threads with new replies.
- Dedupe by `event_id`.
- One Slack app per agent.
- Status hooks: `SessionStart`, `Stop`, and `SessionEnd` run a script that posts to `#pipe-status` and uses `chat.update`.
- Runtime contract: see design brief §5.1. Config: see §5.4.
- The core uses the `Transport` port (design brief §4). The Slack adapter is `transport_slack_*`. The `ToolPolicy` type sits in the `claude` runtime adapter.
