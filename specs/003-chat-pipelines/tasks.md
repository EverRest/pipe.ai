---

description: "Task list for Pipelines from Chat"
---

# Tasks: Pipelines from Chat

**Input**: Design documents from `/specs/003-chat-pipelines/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md. Specs 001 and 002 are implemented (their modules, ports, and fakes exist).

**Mentions**: `escape_mentions` and `mention` in this file mean the functions of the injected `Formatter` of the `Transport` (spec 001 contracts/transport.md). The core has no mention syntax.

**Tests**: Tests are required. Constitution principle VII (NON-NEGOTIABLE): every pure-function business rule has a test task BEFORE its implementation task. The test must fail first. Tests use fakes: no real Slack, no real GitLab, no real Claude.

**Spec 004 note (2026-11-26)**: spec 004 adds `write` steps and the owner gate. The tests T016, T027, T032, and T072 here assert that `write` is refused. The 004 tasks T009, T011, T013, and T020 replace those cases. 003 tasks stay as they are. 004 does not repeat them.

**Organization**: Tasks are grouped by user story. Paths follow the Source Code layout in [plan.md](plan.md). The tasks follow the owner decisions in "Design decisions" of plan.md (Q1 to Q8) and constitution principle XI (the core is capability-agnostic).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US6, from [spec.md](spec.md)
- Test tasks start with "Write failing test".

## Path Conventions

Single project: `src/pipe/`, `tests/unit/`, `tests/integration/`, `tests/fakes.py` at the repository root (same as 001 and 002).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the files. Check the 001 and 002 baseline.

- [ ] T001 Create the empty new files from the plan: `src/pipe/core/pipeline.py`, `src/pipe/core/trust.py`, `src/pipe/core/claim.py`, `src/pipe/core/route.py`, `src/pipe/core/runrequest.py`, `src/pipe/core/render.py`, `src/pipe/core/metrics.py`, `src/pipe/runtime_claude_request.py`, `src/pipe/runtime_exec.py`, `src/pipe/runtime_http.py`, `src/pipe/runtime_select.py`, `src/pipe/cards.py`, `src/pipe/planner.py`, `src/pipe/stepper.py`, `src/pipe/gitlab_io.py`, `src/pipe/metrics_cli.py`
- [ ] T002 Run `pytest tests/unit tests/integration` for specs 001 and 002. All tests must pass before 003 work starts. Do not add a dependency (research.md D14)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Types, config keys, trust primitives, ports, fakes, message text, and the card cache that every story needs

**CRITICAL**: No user story work starts before this phase is complete.

- [ ] T003 [P] Write failing test for the task types in `tests/unit/test_pipeline.py` (data-model.md TaskMsg, FR-020, research.md D4):
  - `ts_key("1700000000.000100")` gives `(1700000000, 100)`. Keys compare as numbers, not as strings.
  - `parse_task` accepts a valid payload with `v` 1, `task_id`, `phase`, `status`, `by`, `hop`, and the optional `access`, `pipeline`, `step`, `next`, `artifacts`, `reason`. A payload with `phase` `step` needs an `access`. A payload with `phase` `plan` has none.
  - `parse_task` returns `None` for: `v` not 1; a `phase`, `access`, or `status` outside the enums; a field named `kind`; `hop` not an integer or less than 0; a missing `task_id`, `by`, or `status`; a `next` without `agent` or `access`; an `artifacts` item that is not an `https://` URL; a `reason` longer than 200 characters.
  - The parser accepts `access: write` (brief §5.2). `route` does not run it in 003 (T027).
  - A plan step may have `agent: "any"` with `capability: "tag:<tag>"`, and an optional `payload` object (at most 2000 characters as canonical JSON). `next.agent` may be `any`. A `payload` that is not an object, or is too large, gives `None`.
- [ ] T004 Implement the frozen dataclasses `Step`, `Pipeline`, `TaskMsg`, `Claim`, `ThreadState`, the events `HumanMessage`, `BotMessage`, `Reaction`, `Click`, `Wake`, `Decision`, and the functions `ts_key` and `parse_task` in `src/pipe/core/pipeline.py` (T003; data-model.md)
- [ ] T005 [P] Write failing test for the new config keys in `tests/unit/test_config.py` (data-model.md Config keys, research.md D21):
  - `work_channel` default is `pipe-work`.
  - `runtime.name` default is `claude`. The allowed values are `claude`, `exec`, and `http`. Any other value is an error.
  - `runtime.claude.owner_tools` default is `[Read, Grep, Glob]`. `runtime.claude.repo_roots` default is `[~/code]` (`~` expanded). Each is a list of non-empty strings. (`deny_rules` default `[]` and the always-present `Bash(git push:*)` are defined and tested in 001.)
  - `runtime.claude.owner_tools`, `runtime.claude.repo_roots`, and `runtime.claude.deny_rules` are defined by spec 001 (T004, T005 of 001; FR-019). 003 adds only `runtime.name` on top and does not define `deny_rules` again. There is no fallback for the old top-level keys: they are an error (001).
  - `mr_state.provider` default is `gitlab`. `mr_state.gitlab.url` is optional and must start with `https://`.
  - `mr_state.gitlab.token` is optional and must have the form `keychain:<service>`. A value such as `glpat-abc` is an error.
  - `step_timeout_min` (001) is unchanged: default 30, minimum 1.
- [ ] T006 Implement the validation of `work_channel`, the `runtime` section, and the `mr_state` section in `src/pipe/config.py` (T005)
- [ ] T007 [P] Write failing test for `trusted_cards` and `check_task_msg` in `tests/unit/test_trust.py` (FR-008, SC-003, research.md D3, D4). The two card-trust checks (the `user` check and the lower-`ts` rule) are confirmed owner decisions. Each has its own test case below:
  - `trusted_cards` keeps a card only if the message has `sender_is_bot` true, the `event_type` is `pipe.card.v1`, `payload.bot_id` equals the message `sender_id`, the message `sender_handle` (when present) equals `payload.bot_user_id`, and `validate_card` (002) returns `[]`. The test builds neutral `Message` values (spec 001 contracts/transport.md). It uses no raw Slack field.
  - It drops a card posted by a person (`sender_is_bot` false), a card with a `bot_id` that differs from `sender_id`, a card with a `sender_handle` that differs from `bot_user_id`, a card with no `bot_user_id`, and a card with a URL in a field.
  - Two cards with the same `bot_user_id`: the card with the lower message `ts` stays, the other is dropped (research.md D3). The order of the input does not change the result.
  - A card message with no `sender_handle` is kept when all other checks pass (assumption A8). Then only the lower-`ts` rule protects the mention.
  - If one bot posted two cards, the one with the highest `ts` wins.
  - `check_task_msg(msg, cards, plan_info)` returns `None` for a valid message. It returns the reason `no_card` for an author without a card, `bad_payload` for a payload that `parse_task` rejects or a `task_id` that differs from the thread, and `by_mismatch` when `by` differs from the author `bot_id`.
  - It returns `not_planner` for a plan message whose `by` is not the planner, and `not_assigned` for a step claim whose `by` is not the agent that the plan assigns to the step.
  - It does not change its input.
- [ ] T008 Implement `trusted_cards` and `check_task_msg` in `src/pipe/core/trust.py` (T007; uses `validate_card` from `src/pipe/core/card.py`)
- [ ] T009 [P] Check that `Transport` (001 `ports.py`, contracts/transport.md) has `replies(channel, thread)` (with `reactions` and cursor), `delete_message(channel, ts)`, and the optional `buttons` argument of `post_message` and `update_message`, and that `on_event` delivers `ReactionEvent` and `ClickEvent`. Add what is missing. Add no method for a bot-to-user lookup (Q7 = b: the card has `bot_user_id`). Add the field `request: RunRequest | None` to `RuntimeInput` (default `None`; contracts/runtime-request.md). Add the Protocol `MrStatePort` with `mr_state(url) -> {state, merged_at} | None` (research.md D11, D17, D19)
- [ ] T010 [P] Extend `tests/fakes.py` (depends on T004, T009):
  - `FakeTransport` gets `replies` (metadata and reactions, `sender_id`, `sender_is_bot`, and `sender_handle` on bot messages, cursor pages of 100), `delete_message`, and `buttons` on post and update. It records every call. It has no bot-to-user lookup method, so a test fails if the adapter calls `bots.info` or `users.info` (SC-012).
  - `FakeTransport` has helpers `add_reaction(channel, ts, sender_id, name)` and `click(channel, ts, sender_id, action_id)` that build the events of the `Reaction` and `Click` types.
  - `FakeMrState` (the `MrStatePort` fake) returns canned `{state, merged_at}` for a URL and records each call and the host of each call.
  - `make_thread(...)` builds a `ThreadState` and the matching `FakeTransport` thread from a short table of messages, cards (with `bot_user_id`), and reactions.
  - A fake clock and a fake timer factory (`FakeTimers.fire_all()`) for `CLAIM_SETTLE_S` and `OWNER_OFFLINE_AFTER_S`.
- [ ] T011 [P] Write failing test for `render_task`, `render_plan`, and `render_errors` in `tests/unit/test_render.py` (contracts/task-metadata.md "Texts", FR-012, SC-007):
  - Each message type of contracts/task-metadata.md gives the text in the contract, with the agent names from the cards.
  - Every text passes `scrub` and the `escape_mentions` of the injected `Formatter` (the test uses the fake one of `FakeTransport`). A token-like string in a goal or a reason becomes `[redacted]`. Broadcast and mention syntax inside a reply text is escaped.
  - Only the mention of the next agent (and of the human approver) is a real mention (`Formatter.mention`). A tag step mentions every eligible agent.
  - A tag step shows `any agent with tag <tag>`. The type 9 message shows `failed. Reason: no_claimer`.
  - A `reason` is cut to 200 characters.
  - No text holds a path or an MCP URL.
- [ ] T012 Implement `render_task`, `render_plan`, and `render_errors` in `src/pipe/core/render.py` (T011; reuses `scrub` and `escape_mentions` from 001)
- [ ] T013 [P] Write failing test for the card cache in `tests/unit/test_cards.py` (research.md D3, D5):
  - The first call reads `#pipe-agents` through `history` and returns the trusted cards.
  - A second call within 5 minutes does not read Slack.
  - After 5 minutes (fake clock), it reads again.
  - A message from an unknown `bot_id` triggers one refresh. A second unknown message within 60 seconds triggers no refresh.
  - `agent_users()` maps the `bot_user_id` of each trusted card to its `bot_id`. It makes no Slack call. It keeps the map in memory (Q7 = b).
  - A bot that has no card is not in the map.
- [ ] T014 Implement `CardCache` in `src/pipe/cards.py` (T013; depends on T008, T009). The mention map comes from the card `bot_user_id`
- [ ] T015 Implement the new `Transport` methods in `src/pipe/transport_slack.py`: `replies` (`conversations.replies` with `include_all_metadata`, cursor pagination), `delete_message` (`chat.delete`), and `buttons` on post and update (T009; the mapping to Block Kit is in `transport_slack_map.py`, 001 T054). Add `reaction_added` and `block_actions` handling to `transport_slack_events.py` (001 T055). Do not call `bots.info` or `users.info`

- [ ] T071 [P] Write failing test for the import boundary in `tests/unit/test_core_boundary.py` (SC-011, FR-024, principle XI). The test reads the source of each core module with `ast`. It first checks that the core files `pipeline.py`, `trust.py`, `claim.py`, `route.py`, `runrequest.py`, `render.py`, `metrics.py`, and `source.py` (003), `gate.py` (004), `trigger.py` (005), `flows.py` (006), and `capability.py`, `exposure.py`, `card.py`, `summary.py`, and `schema.py` (002) exist in `src/pipe/core/` (and `contract.py`, `router.py`, `scrub.py`, `status.py`, `catchup.py`, `dedupe.py` of 001). Then the test globs EVERY `src/pipe/core/*.py` file, so a module that a later spec adds is covered with no change of the test (SC-025, constitution 1.3.0). For all modules of `src/pipe/core/`:
  - No import of `pipe.runtime_claude`, `pipe.runtime_claude_request`, `pipe.runtime_claude_tools`, `pipe.runtime_claude_loadset`, `pipe.runtime_claude_load`, `pipe.runtime_claude_capability`, `pipe.runtime_claude_exposure`, `pipe.runtime_claude_discovery`, `pipe.runtime_exec`, `pipe.runtime_http`, `pipe.runtime_select`, `pipe.declared`, `pipe.gitlab_io`, `pipe.transport_slack`, `pipe.transport_slack_events`, `pipe.transport_slack_map`, `pipe.transport_slack_http`, `pipe.cards`, `pipe.planner`, `pipe.stepper`, or `pipe.adapter`. No import of `slack_bolt` or `slack_sdk`.
  - No string constant and no identifier holds a runtime tool name (`Read`, `Grep`, `Glob`, `Edit`, `Write`, `Bash`, `Skill`), a flag (`--plugin-dir`, `--allowedTools`, `--mcp-config`, `--tools`), or the terms `plugin`, `mcp`, `wiz`, `gitlab`, `glab`, `claude`, `slack`, `discord`, or `telegram`, or the identifiers `ToolPolicy` and `tools_for`. The A2A card field name `skills` and the type name `CardSkill` are allowed. No string constant and no identifier holds a standard tag name: the test reads the tag names from `flows/tags.yaml` when the file exists (spec 006), and it checks a fixed fallback list (`review`, `implement`, `e2e`, `decompose`) when it does not. (The word `review` and the tag names are data, never core constants.) The wire field names `bot_id` and `bot_user_id` are allowed (opaque ids).
  - The test also checks that no module in `src/pipe/core/` (including the 002 modules) imports a `pipe.runtime_claude*` or `pipe.transport_slack*` module, and that `core/contract.py` does not define `ToolPolicy`.
  - The test has three negative cases: a temporary module that holds the string `"review"` as a tag constant makes the checker report an error; a temporary module with `import pipe.runtime_claude` makes the checker report an error; and a temporary module with `import pipe.transport_slack_map` does too.

**Checkpoint**: Foundation ready. User stories can start.

---

## Phase 3: User Story 1 - Plan a pipeline and approve it (Priority: P1) MVP

**Goal**: A message that names two or more agents gives one plan in the thread. A wrong plan is rejected before ✅. Only the thread starter or the planner owner can start it with ✅.

**Independent Test**: Run `pytest tests/unit/test_validate_plan.py tests/unit/test_route_human.py tests/unit/test_route_reaction.py tests/integration/test_plan_flow.py`. Then do the quickstart scenarios "1".

### Tests for User Story 1 (write first, they MUST fail)

- [ ] T016 [P] [US1] Write failing test for `validate_plan` in `tests/unit/test_validate_plan.py` (FR-004, SC-001, data-model.md "Pipeline (plan)", Q2, Q3):
  - A valid plan gives `[]`.
  - An empty `steps` list is an error. A plan with 4 bot steps is an error when its effective source is `free` (the call passes no `flows`, so the limit is 3; T090 to T093 add the template limit 5). A plan with 3 bot steps and one human step is valid.
  - An `access` other than `read` or `approve` is an error. `access: write` gives the error `not supported before spec 004` (FR-025). A step that still has the old fields `kind` or `skill` is an error.
  - A bot step with `access: approve`, a bot step with no `capability`, a human step with `access: read`, and a human step with a `capability` are errors.
  - An `approve` step that is not the last step is an error. Two `approve` steps are an error. A plan whose first step is a human step is an error.
  - A bot agent with no card is an error that names the step number.
  - A `capability` that is not in `cards[agent].skills[].id` is an error (a hidden capability: the card lists exposed capabilities only). A step whose capability has the tag `review` is valid like any other step (the function reads no tag).
  - The test uses opaque IDs (for example `cap-1`) in most cases. This shows that the function treats the capability as an opaque string.
  - An empty `goal`, and a `goal` longer than 500 characters, are errors.
  - A human step whose user is not the `starter` and not the card `owner` of the bot agent of the step before it is an error (Q3). With `starter=None` this rule is skipped.
  - Several errors give several lines. The order follows the step order. The function does not change its input.
- [ ] T017 [P] [US1] Write failing test for `first_agent`, `mentions`, and the `HumanMessage` branch of `route` in `tests/unit/test_route_human.py` (FR-001, FR-002, Q1, data-model.md route rule 1):
  - `mentions(text)` returns the `<@U...>` IDs in text order, without duplicates.
  - `first_agent(text, agent_users)` returns the first mention that maps to a card. A mention of a person or of a bot with no card is skipped.
  - A top-level message with two distinct agent mentions: `plan` for the first agent, `ignore(not_planner)` for the second agent.
  - A top-level message with one agent mention: `chat`. The 001 status query still gives `status_query`.
  - A thread reply with two agent mentions: `chat` for each named agent (one pipeline per thread).
  - A message from a bot, from the agent itself, with no mention of the agent, or with a known `event_id`: `ignore` (001 rules).
  - A top-level message that already has a plan message by this agent (catch-up repeat): `ignore(already_planned)`.
- [ ] T018 [P] [US1] Write failing test for the `Reaction` branch of `route` in `tests/unit/test_route_reaction.py` (FR-006, FR-007, SC-002, data-model.md route rule 3):
  - `white_check_mark` by the thread starter on a trusted plan message (`needs_approval`, by this agent): `start`.
  - The same by the card `owner` of the planner: `start`.
  - The same by another person: `ignore(not_allowed)`.
  - Another emoji: `ignore`.
  - ✅ on a message that is not a plan, on a rejected plan (`failed`), or on the human request: `ignore`.
  - ✅ on a plan message of another agent: `ignore`.
  - ✅ when a start message already exists (second ✅): `ignore(already_started)`.
  - The thread starter is also the planner owner: `start` once.
  - ✅ before the plan message exists: there is no target, `ignore`.
- [ ] T019 [P] [US1] Write failing test for the planner command in `tests/unit/test_runtime_claude.py` with the stub `claude` script (contracts/plan-schema.md). This is a test of the `claude` adapter:
  - `build_cmd(inp, cfg, schema=PLAN_SCHEMA)` for `inp.request = RunRequest((), "read", False)` has `--json-schema` with the plan schema, `--tools ""`, `--restricted`, and `--permission-mode dontAsk`. It has no `--allowedTools`, no `--add-dir`, and no `--plugin-dir`.
  - Without `schema`, the command is the 001 command (no change).
  - `Read(//<root>/**)` path rules appear only when `Read`, `Grep`, or `Glob` is in the tool list. A tool list with `Skill` only has no path rule.
- [ ] T020 [P] [US1] Write failing test in `tests/integration/test_plan_flow.py` with `FakeTransport`, `FakeRuntime`, and a fake card channel (SC-001, SC-002, FR-003, FR-005, FR-021):
  - A request that names two agents gives one type 1 plan message (`needs_approval`, `hop` 0, `pipeline`) from the first agent only. The second adapter posts nothing.
  - The planner prompt holds the card list and the thread as untrusted data. The runtime gets the plan schema and `RunRequest((), "read", False)`, also when the starter is the owner. With the stub `claude`, the command has `--tools ""`.
  - A plan with an unknown agent, a hidden capability, an `access: write` step, or 4 bot steps gives one type 2 message that lists the errors. A ✅ on it starts nothing.
  - A runtime failure or bad JSON gives one type 2 message with the reason (scrubbed, at most 200 characters).
  - ✅ by the thread starter gives one type 3 start handoff (`hop` 1, `next` for step 0, mention `<@bot_user_id>` of the step 1 agent, taken from its card). Two ✅ events (starter and owner) give one start message. `FakeTransport` records no `bots.info` and no `users.info` call (SC-012).
  - ✅ by another person gives no message. A ✅ before the plan exists gives no message.
  - A person edits the request text after the plan: nothing changes.
  - No new file appears under `~/.pipe/` besides the 001 and 002 files (FR-021, principle I).

### Implementation for User Story 1

- [ ] T021 [US1] Implement `validate_plan` and `find_plan` in `src/pipe/core/pipeline.py` (T016; same file as T004). `find_plan` returns the earliest trusted plan message that has a `pipeline` and whose `by` equals the planner
- [ ] T022 [US1] Implement `mentions`, `first_agent`, and the `HumanMessage` and `Reaction` branches of `route` in `src/pipe/core/route.py` (T017, T018; depends on T008, T021). The `HumanMessage` branch calls the 001 `should_handle` rules
- [ ] T023 [P] [US1] Add the `schema` argument to `build_cmd` in `src/pipe/runtime_claude.py` (the `claude` adapter). Add `PLAN_SCHEMA` (contracts/plan-schema.md). Add the path allow rules for a tool only when that tool is in the list (T019)
- [ ] T024 [US1] Implement `run_planner` in `src/pipe/planner.py` (T020; depends on T012, T014, T021, T023): build the prompt, call `RuntimePort.run` with `task = {id, purpose: "plan"}` and `request = RunRequest((), "read", False)` (always, also for the owner: confirmed decision), parse the plan, call `validate_plan(plan, cards, starter)`, and post a type 1 or type 2 message with `render_plan` or `render_errors`
- [ ] T025 [US1] Implement `start_pipeline` in `src/pipe/stepper.py` (T020; depends on T012, T021): post the type 3 start handoff with `hop` 1, `next` for step 0, and the mention `<@bot_user_id>` of the step 1 agent (from its card). Use the in-flight key `start:<channel>:<thread_ts>` For a tag step (T089), the handoff mentions every eligible agent
- [ ] T026 [US1] Wire the work channel in `src/pipe/adapter.py` (T020; depends on T022, T024, T025): register `reaction_added`; build `ThreadState` for each event (`replies`, card cache, 001 seen set); call `route`; run the `plan` decision on the worker queue; run the `start` decision. A `chat` decision keeps the 001 flow

**Checkpoint**: User Story 1 works. A plan appears and starts with ✅.

---

## Phase 4: User Story 3 - Reject untrusted and looping input (Priority: P1)

**Goal**: An adapter acts only on trusted task data. It refuses `hop` 4. It stops a loop. This phase comes before User Story 2 because the guard protects every handoff.

**Independent Test**: Run `pytest tests/unit/test_route_bot.py tests/unit/test_hop_rule.py tests/integration/test_trust_hop.py`. Then do the quickstart scenarios "3".

### Tests for User Story 3 (write first, they MUST fail)

- [ ] T027 [P] [US3] Write failing test for the `BotMessage` branch of `route` in `tests/unit/test_route_bot.py` (FR-001, FR-008, FR-009, SC-003, SC-004, data-model.md route rule 2):
  - A handoff from a bot with no card: `ignore(no_card)`.
  - A payload with a wrong `v` or a bad enum: `ignore(bad_payload)`. A `by` that differs from the author: `ignore(by_mismatch)`.
  - `next.agent` is another agent: `ignore(not_for_me)`.
  - Free plan (no `flows`): `hop` 3: `claim`. `hop` 4: `refuse`. `hop` 4 from a bot with no card: `ignore(no_card)` (not `refuse`). The limit for a verified template is tested in T092.
  - The plan does not assign the step to this agent: `ignore(not_assigned)`. The plan was posted by a bot that is not the planner: `ignore(not_planner)`.
  - The `next.access` is `write` or `approve`: `ignore(unsupported_access)`.
  - This agent already has a claim for the step after the handoff, or the step key is in flight: `ignore(already_claimed)`.
  - A task message with no `next`: `ignore`.
- [ ] T028 [P] [US3] Write failing test for `next_hop` and the hop rule in `tests/unit/test_hop_rule.py` (FR-009, FR-010, research.md D6): — closed: covered by route and stepper tests (see the tests)
  - `next_hop(h)` is `h + 1`. The approval request keeps the `hop` of its claim.
  - Free plan: a chain A to B (hop 1), B to A (hop 2), A to B (hop 3) is accepted. The next handoff (hop 4) is refused. (A verified template has the limit 5: T092.)
  - In every accepted chain, the number of back-and-forth handoffs (a handoff to the agent that handed over the step before) is at most 2 (FR-010).
  - `validate_plan` accepts at most `hop_limit(effective_source)` bot steps (3 for a free plan), so a valid plan never reaches a `hop` above its limit.
- [ ] T029 [P] [US3] Write failing test in `tests/integration/test_trust_hop.py` (SC-003, SC-004):
  - A message with `pipe.task.v1` metadata from a bot with no card causes no claim, no run, and no post (US3 scenario 1).
  - A handoff with `hop` 4 from a bot with a card gives one type 8 message (`failed`, `hop limit exceeded`) and no runtime call. The same event twice gives one refusal.
  - A refused thread stops: no later message from this thread starts work.
  - `hop` 4 sent by a bot with no card gives no refusal message.
  - A person posts a message that looks like task metadata in its text: no effect.

### Implementation for User Story 3

- [ ] T030 [US3] Implement `next_hop` and the `BotMessage` branch of `route` in `src/pipe/core/route.py` and `src/pipe/core/pipeline.py` (T027, T028; depends on T008, T021, T022)
- [ ] T031 [US3] Implement `refuse` in `src/pipe/stepper.py` and wire `BotMessage` events in `src/pipe/adapter.py` (T029; depends on T030): post the type 8 message once (in-flight key `refuse:<channel>:<ts>`), run nothing, and save `last_seen_ts`

**Checkpoint**: User Stories 1 and 3 work.

---

## Phase 5: User Story 2 - Run the steps one by one (Priority: P1)

**Goal**: After ✅, each agent runs its step in the same thread. A step starts only after the step before is `done`. Each state shows in the thread. The last step can be a human approval with a button. A step that another person started cannot call an `owner-only` tool.

**Independent Test**: Run `pytest tests/unit/test_runrequest.py tests/unit/test_runtime_claude_request.py tests/unit/test_thread_status.py tests/unit/test_route_click.py tests/integration/test_run_steps.py`. Then do the quickstart scenarios "2".

### Tests for User Story 2 (write first, they MUST fail)

- [ ] T032 [P] [US2] Write failing test for `build_run_request` in `tests/unit/test_runrequest.py` (FR-022, FR-025, FR-027, SC-009, research.md D9, Q5, Q6). The core module names no tool and no flag:
  - A `read` bot step started by the owner (`starter == owner`): `RunRequest((<capability>,), "read", True)`.
  - The same step started by another person: `requester_is_owner` is false.
  - `owner` empty or `None`: `requester_is_owner` is false for every starter (fail closed).
  - `capabilities` holds the step `capability` and nothing else. The ID is an opaque string (the test uses `cap-1`).
  - An `approve` step raises `ValueError` (no runtime runs). A `write` step raises `ValueError`.
  - The planner request is `RunRequest((), "read", False)`, also when the thread starter is the owner (confirmed decision). The test checks the helper `planner_request()`.
  - The result has no field with a tool name, a path, or a flag.
  - The function does not change its input.
- [ ] T033 [P] [US2] Write failing test for `step_status` and `thread_status` in `tests/unit/test_thread_status.py` (FR-011, FR-012, FR-013, data-model.md "Status of a step and of a thread"): — closed: covered by route and stepper tests (see the tests)
  - `step_status` is the status of the latest trusted message with the same `step`, by `ts` as numbers. The plan message is not a step message. No message gives `pending`.
  - `thread_status` gives `needs_approval`, `rejected`, `running`, `waiting`, `failed`, and `done` for the matching threads.
  - A thread is `done` when the last bot step has a type 5 message with no `next`. A thread with a human last step is `done` only after the approval message is `done`.
  - Step 2 is not startable while step 1 is not `done` (`next_step_ready`).
- [ ] T034 [P] [US2] Write failing test for the `Click` branch (approve) of `route` in `tests/unit/test_route_click.py` (FR-013, FR-007, Q3, data-model.md route rule 4):
  - Approve click by the thread starter on a type 6 message by this agent: `approve`.
  - The same by the card `owner` of this agent: `approve`.
  - The same by another person, including the named `human:<user_id>` when that person is neither: `ignore(not_allowed)`.
  - A click on a message of another agent, on a type 6 message that is already `done`, or with an unknown `action`: `ignore`.
- [ ] T035 [P] [US2] Write failing test in `tests/integration/test_run_steps.py` with two adapters, `FakeTransport`, and `FakeRuntime` (SC-007, SC-009, FR-011 to FR-013, FR-022):
  - Approved plan with two bot steps and one human step: step 1 posts `claimed`, `running`, `done`. Step 2 starts only after step 1 is `done`. Step 2 ends. The approval request has a button. The thread ends `done` after the click.
  - The runtime of a `read` step gets `task = {id, purpose: "step", step, pipeline: {goal}}`, the thread as untrusted text, and `request = RunRequest((<capability>,), "read", <bool>)`. It gets no `hop`, `from_agent`, `owner`, or trust data (principle VI).
  - The goal and the capability come from the plan, not from `next.payload` (a changed `next.payload` has no effect).
  - A step started by the owner gets `requester_is_owner` true. A step started by another person gets false. With the stub `claude` (the real `claude` adapter), the owner command has `runtime.claude.owner_tools`, and the other command has `--tools ""` plus the `Skill` tool, no `Read`, `Grep`, or `Glob`, and no `owner-only` rule.
  - The `claude` adapter calls `prepare` before the run and `cleanup` after it, also after a runtime failure (checked here with the stub and in T072).
  - The reply text is scrubbed. Mentions in it are escaped. `artifacts` are in the result message.
  - A runtime status other than `done` gives `failed` with `reason: runtime status <s>` and no next handoff.
  - The approval click by the thread starter gives `done`. A click by another person changes nothing.
  - A step whose capability has the tag `review` runs like any other step and ends when its agent posts `status: done` (no review-specific path).
  - Every state change is visible in the thread text (SC-007).
  - `last_seen_ts` moves forward only after the step ends.
- [ ] T072 [P] [US2] Write failing test for `map_request` and the run path of the `claude` adapter in `tests/unit/test_runtime_claude_request.py` and `tests/unit/test_runtime_claude.py` with the stub `claude` script (FR-022, FR-027, SC-009, research.md D9, contracts/runtime-request.md, Q5). This is a test of the `claude` adapter, not of the core:
  - `requester_is_owner` true, `access` `read`: `tools` = `runtime.claude.owner_tools`, `restricted=True`, load set = the requested capability (if exposed). `--allowedTools` has the path rules for `runtime.claude.repo_roots`.
  - `requester_is_owner` false: `tools=[]`, `allowed=[]`, `restricted=True`. The load set holds exposed items only. The command has `--tools ""` plus `Skill` when a skill or command loads.
  - `access: read` removes `Edit`, `Write`, and `NotebookEdit` from `tools` and puts them in `disallowed`, also when the owner widened `runtime.claude.owner_tools`.
  - `access: write` raises `ValueError`. `run` turns it into `RuntimeFailed`.
  - A capability that is `owner-only` and not exposed, or not discovered, is not in the load set. The run fails with `reason: capability not available`.
  - `disallowed` holds `mcp__<server>` for each `owner-only` MCP server, `Skill(<name>)` for each `owner-only` skill or command, and every entry of `effective_deny_rules(runtime.claude.deny_rules)`. A custom `deny_rules` list ADDS to the default: `Bash(git push:*)` is always in `disallowed` (001 T057, FR-019).
  - Property: for random capability sets and `requester_is_owner` false, no `owner-only` rule is in `allowed`, and every `owner-only` rule is in `disallowed`.
  - `run(inp)` with `inp.request` set calls `prepare` before the child and `cleanup` after it, also after a failure and after a timeout. With `inp.request = None` the command is the 001 command (regression).
  - `request.output_schema` set: `build_cmd` merges it as the schema of the property `data` into the `--json-schema` value. `output_schema` `None`: the 001 value (no change).
  - The function does not change its input.

### Implementation for User Story 2

- [ ] T036 [P] [US2] Implement `RunRequest`, `build_run_request`, and `planner_request` in `src/pipe/core/runrequest.py` (T032). The module imports no runtime-specific module and no transport module. After T075 it imports `core/schema.py` (002) for `check_input` and `check_output`
- [ ] T037 [US2] Implement `step_status`, `thread_status`, and `next_step_ready` in `src/pipe/core/pipeline.py` (T033; same file as T004)
- [ ] T038 [US2] Implement the `Click` approve branch of `route` in `src/pipe/core/route.py` (T034; same file as T022)
- [ ] T039 [US2] Implement `claim_step` in `src/pipe/stepper.py` (T035; depends on T012, T031): post the type 4 claim at receipt (`claimed`) and queue the run. No contest check yet (T047 adds it)
- [ ] T040 [US2] Implement `run_step` in `src/pipe/stepper.py` (T035; depends on T036, T039): update the claim to `running`; call `build_run_request` and `RuntimePort.run` (`task` as in contracts/plan-schema.md, plus `request`); read the goal and the capability from the plan. The stepper does not call `prepare` or `cleanup`: the runtime adapter does (T073) T083 adds the tag binding, the schema checks, and the runtime selection to this function
- [ ] T041 [US2] Implement `finish_step` in `src/pipe/stepper.py` (T035; depends on T040): update the claim to `done`; post the type 5 result with the scrubbed text, `artifacts`, `hop + 1`, and `next` plus the mention, or post the type 6 approval request with the button (`pipe_approve`), or post the final type 5 with no `next`
- [ ] T042 [US2] Implement `approve_step` in `src/pipe/stepper.py` (T035; depends on T038, T041): set the type 6 message to `done`, remove the button, and use the in-flight key `approve:<channel>:<ts>`
- [ ] T043 [US2] Wire the worker jobs and the `block_actions` handler in `src/pipe/adapter.py` (T035; depends on T039 to T042): route each click through `route`; run `claim_step`, `run_step`, and `finish_step` on the worker queue (one runtime call at a time); save `last_seen_ts` after the step ends

- [ ] T073 [US2] Implement `map_request` in `src/pipe/runtime_claude_request.py` and the request path of `run` in `src/pipe/runtime_claude.py` (T072; depends on T036 and on the 002 tasks T022 to T024): map `RunRequest` to `StepTools(policy, load)` with `load_set(caps, exposed, request.capabilities)`; remove the write tools for `access: read`; add the `deny_rules`; refuse `access: write`; call `prepare` before the child and `cleanup` in a `finally`. These are the only place where tool names and flags are built for a step

**Checkpoint**: User Stories 1, 3, and 2 work. A full pipeline runs.

---

## Phase 6: User Story 4 - Resolve duplicate claims (Priority: P2)

**Goal**: When two adapters claim one step, the claim with the lowest `ts` wins and the other adapter stops.

**Independent Test**: Run `pytest tests/unit/test_claim.py tests/integration/test_claims.py`. Then do the quickstart scenario "4".

### Tests for User Story 4 (write first, they MUST fail)

- [ ] T044 [P] [US4] Write failing test for `resolve_claim` in `tests/unit/test_claim.py` (FR-014, SC-005, data-model.md Claim):
  - Two claims: the lowest `ts` wins. The order of the input does not change the result.
  - `ts` compares as numbers: `1700000000.000900` is lower than `1700000000.001000`, and `999.000001` is lower than `1000.000001`.
  - Two claims with the same `ts`: the lower `by` string wins.
  - Claims with status `failed` are dropped. A list with only `failed` claims, and an empty list, give `None`.
  - Three claims give one winner. The function does not change its input.
- [ ] T045 [P] [US4] Write failing test in `tests/integration/test_claims.py` with two adapters that use the same bot (FR-014, SC-005, US4 scenario 2):
  - Both adapters get the handoff. Both post a claim. After `CLAIM_SETTLE_S`, the claim with the lowest `ts` runs. The other adapter deletes its claim and calls no runtime.
  - Exactly one runtime call happens (SC-005).
  - A claim with status `failed` from a first attempt does not block the claim after a "Retry".
  - If a lower claim appears after the first check, the adapter that is not the winner drops its result at the final check and posts no result message.
  - A claim by an agent that the plan does not assign to the step is ignored.

### Implementation for User Story 4

- [ ] T046 [US4] Implement `resolve_claim` in `src/pipe/core/claim.py` (T044)
- [ ] T047 [US4] Add the contest to `claim_step` and the final check to `finish_step` in `src/pipe/stepper.py` (T045; depends on T041, T046): wait `CLAIM_SETTLE_S`, read the thread, call `resolve_claim` on the claims of the step, delete the own claim and stop if it lost, and check once more before the result post

**Checkpoint**: User Stories 1 to 4 work.

---

## Phase 7: User Story 5 - Handle a hung step (Priority: P2)

**Goal**: A step that runs too long fails with a reason and a "Retry" button. No retry is automatic. A step whose adapter was interrupted is failed at the next start. A step for an offline owner shows `waiting`. An adapter that restarts continues its open steps.

**Independent Test**: Run `pytest tests/unit/test_route_wake.py tests/unit/test_catchup.py tests/integration/test_timeout_retry.py tests/integration/test_catchup_pipeline.py`. Then do the quickstart scenarios "5".

### Tests for User Story 5 (write first, they MUST fail)

- [ ] T048 [P] [US5] Write failing test for the `Click` retry branch and the `Wake` branch of `route` in `tests/unit/test_route_wake.py` (FR-015 to FR-017, FR-019, research.md D12):
  - Retry click by the thread starter or the card owner of this agent on a `failed` step message (type 4) by this agent: `retry`.
  - The same by another person, on a type 8 message, on a step that has a later claim, or on a step of another agent: `ignore`.
  - `Wake`: an own step with status `claimed` or `running` whose step key is not in flight gives `interrupt`. The same step with its key in flight gives `ignore`.
  - `Wake`: an open handoff for this agent with no claim gives `claim`. A plan by this agent with an allowed ✅ and no start message gives `start`. A top-level request that names this agent as the planner and has no plan message gives `plan`.
  - `Wake` never touches a step of another agent.
- [ ] T049 [P] [US5] Write failing test for the change of `pick_missed` in `tests/unit/test_catchup.py` (FR-019, research.md D13):
  - A bot message that has a mention of this agent and valid task metadata is kept (it goes to `route`). A bot message with no task metadata is still dropped.
  - A handoff with a claim by this agent after it is dropped.
  - 001 cases for human mentions are unchanged.
- [ ] T050 [P] [US5] Write failing test in `tests/integration/test_timeout_retry.py` with `FakeRuntime` that raises `RuntimeFailed("timeout")`, the fake clock, and `FakeTimers` (FR-015 to FR-017, SC-006, US5 scenarios 1 to 4):
  - A step that times out becomes `failed`, `reason: timeout`, with a "Retry" button, in the same pass that the runtime wrapper reports the timeout (less than one minute after the limit; the test asserts that no other delay exists).
  - No second run starts without a click (FR-016).
  - "Retry" by the thread starter gives a new claim with the same `hop`, and a new run. "Retry" by another person gives nothing.
  - The failed reason is scrubbed and has at most 200 characters.
  - The sender of a handoff posts `waiting`, `owner offline` after `OWNER_OFFLINE_AFTER_S` when no claim exists (type 7). No `waiting` message appears when a claim exists.
  - After the late claim, the metrics input has both `ts` values (the wait time is recorded).
  - `Wake` at start fails an own `running` step with `reason: interrupted` and a "Retry" button. `Wake` after a reconnect does not touch a step that is in flight.
- [ ] T051 [P] [US5] Write failing test in `tests/integration/test_catchup_pipeline.py` (FR-018, FR-019, US edge cases):
  - An adapter is down while a handoff for it is posted. At start, it claims and runs the step once.
  - A second restart gives no second run.
  - A ✅ that was added while the planner was down starts the pipeline once at start.
  - The same Slack event twice gives one claim (FR-018).
  - A mention of the planner that arrived while it was down gives one plan.
  - An adapter that restarts in the middle of a pipeline and finds an open step for itself continues it.

### Implementation for User Story 5

- [ ] T052 [US5] Implement the `Click` retry branch and the `Wake` branch of `route` in `src/pipe/core/route.py` (T048; same file as T022)
- [ ] T053 [US5] Implement the failure path in `src/pipe/stepper.py` (T050; depends on T040): on `RuntimeFailed` or a non-`done` status, update the claim to `failed` with the scrubbed `reason` (at most 200 characters) and the `pipe_retry` button. No retry starts alone
- [ ] T054 [US5] Implement `retry_step` in `src/pipe/stepper.py` (T050; depends on T047, T052, T053): remove the button, start a new claim for the same step with the same `hop`, and use the in-flight key `retry:<channel>:<ts>`
- [ ] T055 [US5] Change `pick_missed` in `src/pipe/core/catchup.py` and the `catch_up` pass in `src/pipe/adapter.py` (T049, T051; depends on T052): keep bot messages with task metadata and a mention of this agent; build `ThreadState` for each thread; synthesize the events (`HumanMessage`, `BotMessage`, `Reaction` from the `reactions` field, `Wake`); call `route` for each. Save `last_seen_ts` after the step ends
- [ ] T056 [US5] Run the `Wake` pass at start and after each Socket Mode reconnect in `src/pipe/adapter.py` (T050; depends on T052, T055). One `Wake` job waits at most in the queue (same rule as `catch_up`). The step keys of the running step are in the in-flight set
- [ ] T057 [US5] Implement the offline timer in `src/pipe/stepper.py` (T050; depends on T041): after a handoff post, start a timer of `OWNER_OFFLINE_AFTER_S` (injected factory). When it fires, read the thread and post the type 7 message if no valid claim exists This timer is for a fixed agent (60 seconds, `waiting`, `owner offline`). A tag step uses the `no_claimer` timer of T089

**Checkpoint**: User Stories 1 to 5 work.

---

## Phase 8: User Story 6 - Measure the experiment (Priority: P3)

**Goal**: One script reads `#pipe-work` and an MR-state provider (GitLab first) and prints the four experiment metrics.

**Independent Test**: Run `pytest tests/unit/test_metrics.py tests/unit/test_gitlab_io.py tests/integration/test_metrics_cli.py`. Then do the quickstart scenario "6" and section 3.

### Tests for User Story 6 (write first, they MUST fail)

- [ ] T058 [P] [US6] Write failing test for `compute_metrics` and `render_metrics` in `tests/unit/test_metrics.py` (FR-023, SC-010, data-model.md Metrics):
  - `delegations_per_week`: a step with a merged MR and an agent owner who is not the thread starter counts in the ISO week of `merged_at`. An open MR, a closed MR, an MR of the thread starter own agent, and an MR with no state do not count.
  - `clean_pipelines_share`: a `done` pipeline with no `failed` step and no human message after the start counts as clean, also if a step was `waiting` (Q8 = a). A `done` pipeline with a "Retry" step does not. A `done` pipeline with a human message after the start does not. The approval click is not a message and does not count (Q8 = a). A pipeline stopped by `hop limit exceeded` is in the denominator and is not clean. A `running` pipeline is not counted. An empty denominator gives `n/a`.
  - `noisy_share`: agent messages with a `mute` reaction divided by all trusted agent messages. `hop_stops` counts threads with a `hop limit exceeded` message.
  - `owner_offline_wait_median`: the median of (first later claim `ts` minus `waiting` `ts`) for closed waits. An open wait is counted separately. No closed wait gives `n/a`.
  - A human thread reply that answered a dialog question (spec 003 FR-036) is not manual help: a done pipeline with only such replies is clean (default U6, open for the owner). A ✅ release is not a message.
  - Messages from bots with no card are not counted.
  - `render_metrics` prints the value, the threshold, and `ok`, `below`, or `track`. It prints no thread text.
- [ ] T059 [P] [US6] Write failing test for the GitLab provider of `MrStatePort` in `tests/unit/test_gitlab_io.py` (research.md D17, A6). The provider is the first implementation and is replaceable:
  - `mr_state(url)` for a URL on the configured host returns `{state, merged_at}` with `state` in `open`, `merged`, `closed` (the provider maps the GitLab value `opened` to `open`). The request has the header `PRIVATE-TOKEN` and the path `/api/v4/projects/<url-encoded path>/merge_requests/<iid>`.
  - A URL on another host gives `None` and makes no request. The token is sent only to the configured host.
  - A 404, a timeout, or bad JSON gives `None`. No error text holds the token.
  - It uses `urllib` from the standard library (no new dependency).
- [ ] T060 [P] [US6] Write failing test in `tests/integration/test_metrics_cli.py` with `FakeTransport`, `FakeMrState`, and a test channel of known threads (SC-010, US6 scenarios 1 to 4):
  - The channel has: two merged-MR delegations between owners in one week, one open MR, three pipelines (two clean, one with a "Retry"), two noisy messages among ten, one hop stop, and two waits (one closed with a known length, one open).
  - `pipe metrics` prints the expected values and verdicts.
  - Without the `mr_state.gitlab` config, the delegation line says `n/a (MR state provider not configured)` and the other lines print. The test for `compute_metrics` uses a provider-neutral state map.
  - The output has no token, no thread text, and no MR title. The test channel read uses no database file.

### Implementation for User Story 6

- [ ] T061 [P] [US6] Implement `compute_metrics` and `render_metrics` in `src/pipe/core/metrics.py` (T058; uses `statistics.median`)
- [ ] T062 [P] [US6] Implement the GitLab provider of `MrStatePort` over `urllib` in `src/pipe/gitlab_io.py` (T059; token from `keychain.py` of 001; config `mr_state.gitlab`)
- [ ] T063 [US6] Implement `src/pipe/metrics_cli.py` and the `pipe metrics [--weeks N]` command in `src/pipe/cli.py` (T060; depends on T014, T061, T062): read history and replies of the work channel with metadata and reactions, keep trusted task messages, read each MR state once, call `compute_metrics`, print

**Checkpoint**: All user stories work.

---

## Phase 8A: User Story 7 - Late binding by tag (Priority: P2)

**Goal**: A plan step can name `agent: any` and `capability: tag:<tag>`. Any eligible agent can claim it. The lowest claim `ts` wins. If nobody claims, the sender posts `no_claimer` with a "Retry" button.

**Independent Test**: Run `pytest tests/unit/test_validate_plan_tags.py tests/unit/test_route_tags.py tests/integration/test_tag_steps.py`. Then do the quickstart scenarios "7".

### Tests for User Story 7 (write first, they MUST fail)

- [ ] T084 [P] [US7] Write failing test for the tag rules of `validate_plan` and the helpers in `tests/unit/test_validate_plan_tags.py` (FR-028, FR-029, SC-013, research.md D22, data-model.md rules 10 to 12). Use opaque IDs and tags:
  - `access_fits(step_access, cap_access)`: `None` fits `read` and `write`. `read` fits `read`. `read` does not fit `write`. `write` does not fit `read`.
  - `matches_tag(card, tag, access)`: true when one `skills[]` entry has the tag and a fitting access. False for a tag that no entry has, for an entry with another access, and for an empty card.
  - A plan with a tag step (`agent: any`, `capability: tag:review`) and one card that has the tag is valid. The same plan with no card that has the tag gives `step N: no agent offers tag review`.
  - `agent: any` with a normal ID, and `tag:review` with a named agent, are errors. A bad tag form (`tag:Review`, `tag:`, a tag longer than 32 characters) is an error. `any` with `access: approve` is an error.
  - A tag step counts for the limit of 3 bot steps. A tag step with a `payload` is valid. A `payload` on an `approve` step, or one that is larger than 2000 characters, is an error.
  - A fixed step whose capability is on the card but whose card `access` does not fit the step access is an error (rule 6).
  - A human step after a tag step is valid only when its user is the thread starter. The owner of another agent does not qualify (rule 12).
  - `bind_step(step, caps, exposed, tag_map)`: a tag step becomes a step with the lowest exposed capability ID that has the tag (card tags, `resolve_tags`) and a fitting access. It returns `None` when none exists. An `owner-only` capability never binds. A fixed step is returned as it is.
  - `step_agent(thread, i)` gives the plan agent for a fixed step, the `by` of the winning claim for a tag step, and `None` before a claim.
  - The functions do not change their input. A review tag is only a string: nothing reads its meaning.
- [ ] T086 [P] [US7] Write failing test for tag steps in `route` and `check_task_msg` in `tests/unit/test_route_tags.py` (FR-030, SC-014, research.md D22, D4):
  - A handoff with `next.agent: any` for a tag step: `claim` when the own card matches the tag and the access. `ignore(not_eligible)` when it does not match.
  - A handoff with `next.agent: any` for a fixed step in the plan: `ignore(not_assigned)`.
  - `hop` 4 gives `refuse` for an eligible agent and `ignore(not_eligible)` for an agent that is not eligible.
  - `check_task_msg`: a claim `by` an agent whose card does not match the tag gives `ignore(not_assigned)`. A claim `by` an eligible agent is valid.
  - After a winning claim, a type 5 or type 6 message for the step `by` another eligible agent gives `ignore(not_assigned)` (`step_agent`). The same message `by` the winner is valid.
  - An own claim after the handoff gives `ignore(already_claimed)`.
- [ ] T088 [P] [US7] Write failing test in `tests/integration/test_tag_steps.py` with two or three adapters, `FakeTransport`, and `FakeRuntime` (FR-030, FR-031, SC-014, SC-015, US7 scenarios 1 to 5):
  - A request names no agent for step 2. The planner builds a tag step. The type 1 message shows the tag step. A plan with a tag that no card offers gives one type 2 message and a ✅ starts nothing.
  - The handoff text mentions every eligible agent and no other agent. The mention comes from the card `bot_user_id` through `Transport.mention`.
  - Two eligible adapters claim. After `CLAIM_SETTLE_S`, the lowest claim `ts` runs the step. The other deletes its claim. One runtime call happens. A later message of the step from the loser is ignored.
  - An adapter without the tag does nothing.
  - The winner binds the lowest exposed capability with the tag. `FakeRuntime` gets `RunRequest((<bound id>,), ...)`.
  - No claim within `step_timeout_min` (fake timer): the sender posts type 9 (`failed`, `no_claimer`, "Retry" button). No runtime runs. A "Retry" click by the thread starter posts the handoff again with the same `hop`. A click by another person changes nothing. The step then runs once.
  - A human approval step after a tag step: the plan is valid only when the human is the thread starter.
  - A `write` tag step: the winner faces the gate of spec 004 (checked in the 004 test T052).

### Implementation for User Story 7

- [ ] T085 [US7] Implement `access_fits`, `matches_tag`, `bind_step`, `step_agent`, and the tag rules of `validate_plan` in `src/pipe/core/pipeline.py` (T084; same file as T004, T021, T037)
- [ ] T087 [US7] Implement the tag branch of `route` in `src/pipe/core/route.py` and the tag checks of `check_task_msg` in `src/pipe/core/trust.py` (T086; depends on T085; same files as T022, T008)
- [ ] T089 [US7] Implement the tag handoff in `src/pipe/stepper.py` and `src/pipe/planner.py` (T088; depends on T087, 002 T061): `start_pipeline` and `finish_step` mention every eligible agent for a tag step; `claim_step` calls `bind_step` after the contest; the `no_claimer` timer (`step_timeout_min`, injected factory) posts type 9 with `pipe_retry`; `retry_step` posts the handoff again for type 9; the planner prompt gets the tag rule and the card tags (contracts/plan-schema.md)

**Checkpoint**: User Story 7 works.

---

## Phase 8B: User Story 8 - Run a declared capability with optional schemas (Priority: P2)

**Goal**: A step for a declared `exec` or `http` capability runs through its own adapter. The core checks the `payload` and the result against the optional schemas.

**Independent Test**: Run `pytest tests/unit/test_runtime_exec.py tests/unit/test_runtime_http.py tests/unit/test_runtime_select.py tests/unit/test_runrequest.py tests/integration/test_declared_steps.py`. Then do the quickstart scenarios "8".

### Tests for User Story 8 (write first, they MUST fail)

- [ ] T074 [P] [US8] Write failing test for `pick_runtime`, `check_input`, `check_output`, and the `output_schema` of `build_run_request` in `tests/unit/test_runrequest.py` (same file as T032; FR-032 to FR-034, research.md D23, D24):
  - `pick_runtime(caps, id, default)` gives the `runtime` of the capability with that ID. An empty ID gives `default`. An unknown ID raises `LookupError`.
  - `check_input(step, cap)`: a capability with no `input_schema` gives `None`, with any payload. A payload that matches gives `None`. A payload that does not match gives `invalid_payload` with error sentences that hold no value. A missing payload counts as `{}`.
  - `check_output(output, cap)`: no `output_schema` gives `None`. A matching `data` gives `None`. A bad or missing `data` gives `invalid_result`.
  - `build_run_request(step, starter, owner, output_schema)` copies `output_schema`. Without it, the field is `None`. The result still holds no path, tool name, or flag.
  - The functions do not change their input.
- [ ] T076 [P] [US8] Write failing test for the `exec` adapter in `tests/unit/test_runtime_exec.py` with small scripts in `tmp_path` (FR-034, runtime-exec-http.md):
  - The adapter starts the command from an argv list with no shell: a `command` item such as `; rm -rf /` or `$(id)` stays one argument.
  - The JSON input is on stdin: `goal`, `payload`, `task`, and `output_schema` (only when they exist). It holds no thread text.
  - The child environment holds only the variables of `env_allow` and `PIPE_RUNTIME=1`. A variable that is not in the list (for example a fake `SLACK_TOKEN` set in the test process) is absent. Without `env_allow`, the environment is `PIPE_RUNTIME=1` only.
  - The working directory is an empty directory that is removed after the run, also after a failure and a timeout.
  - A valid stdout `{text, status, next?, artifacts?, data?}` gives a `RuntimeOutput`. Bad JSON, a missing `text`, a bad `status`, and an output over 1 MB raise `RuntimeFailed`.
  - A non-zero exit raises `RuntimeFailed("exit <code>")`. A timeout kills the process group and raises `RuntimeFailed("timeout")`.
  - `text` with a token-like string becomes `[redacted]`. `text` with mention syntax is escaped (fake `Formatter`). `artifacts` that are not `https://` links are dropped.
  - The adapter refuses a capability that is not declared, or that is not exposed now (for `requester_is_owner` true and false): `RuntimeFailed("capability not available")`. The script does not run.
  - No log line, exception, or reason holds an argv item, an environment value, or a token. The first 200 scrubbed characters of stderr go to the log only.
- [ ] T078 [P] [US8] Write failing test for the `http` adapter in `tests/unit/test_runtime_http.py` with a local `http.server` thread on `127.0.0.1` (FR-034, runtime-exec-http.md):
  - The adapter sends one `POST` with `Content-Type: application/json` and the JSON input as the body.
  - With `token: keychain:<service>`, the adapter reads the token through `FakeKeychain` (account `token`) and sends `Authorization: Bearer <token>`. Without `token`, no header is sent. The token goes only to the configured host.
  - A redirect (302) is not followed and gives `RuntimeFailed("http 302")`. A status code outside 200 to 299 gives `RuntimeFailed("http <code>")`.
  - A valid body gives a `RuntimeOutput`. A bad body, a body over 1 MB, and a timeout raise `RuntimeFailed`.
  - Output scrub and escape, and the refusal of a capability that is not exposed now, are the same as for `exec` (T076).
  - No log line, exception, or reason holds the URL path, the query, or the token. A log line may hold the host name.
- [ ] T080 [P] [US8] Write failing test for the selector in `tests/unit/test_runtime_select.py`:
  - A request with a `claude` capability goes to the `claude` adapter. An `exec` capability goes to the `exec` adapter. An `http` capability goes to the `http` adapter. A request with no capability and no `request` (chat, planner) goes to the default `runtime.name`.
  - An unknown capability ID raises `RuntimeFailed("capability not available")`. No adapter runs.
  - The selector calls `pick_runtime` and holds no other rule.
- [ ] T082 [P] [US8] Write failing test in `tests/integration/test_declared_steps.py` with `FakeTransport`, the real `exec` adapter, a script, and a fake `http` server (FR-032 to FR-034, SC-016, SC-017, US8 scenarios 1 to 5):
  - A step for a declared `exec` capability runs the script. The result has the scrubbed `text` and the `artifacts`. The step ends `done`.
  - A capability with an `input_schema` and a bad `payload`: the step is `failed`, `reason: invalid_payload`. The script did not run. No gate request is posted (the check runs before the gate).
  - A capability with an `output_schema` and a script that returns a bad `data`: the step is `failed`, `reason: invalid_result`. A good `data` gives `done`.
  - A capability with no schema behaves as before (also with a `payload`).
  - A step started by a person who is not the owner, for a capability that is not exposed now: `failed`, `capability not available`. The script did not run.
  - The `claude` path still runs for a `claude` capability in the same pipeline (mixed pipeline: one `claude` step, one `exec` step).
  - The child environment holds no variable of the adapter that is not in `env_allow`.

### Implementation for User Story 8

- [ ] T075 [US8] Implement `pick_runtime`, `check_input`, `check_output`, and the `output_schema` field in `src/pipe/core/runrequest.py` (T074; depends on 002 T055; same file as T036)
- [ ] T077 [US8] Implement the `exec` adapter in `src/pipe/runtime_exec.py` (T076; depends on 001 T009, T010 and 002 T057): `RuntimePort` over `subprocess`, argv list, minimal environment, `~/.pipe/run/<run_id>/` working directory, timeout with process-group kill, result size limit, `parse_output`, `scrub`, `escape_mentions`
- [ ] T079 [US8] Implement the `http` adapter in `src/pipe/runtime_http.py` (T078; depends on 001 T009, T010, T011 and 002 T057): `RuntimePort` over `urllib.request` with a redirect handler that refuses redirects, Keychain token by name (`keychain.py` of 001), timeout, result size limit
- [ ] T081 [US8] Implement `RuntimeSelector` in `src/pipe/runtime_select.py` (T080; depends on T075, T077, T079) and wire it in `src/pipe/cli.py` and `src/pipe/adapter.py` (the composition root builds the adapters and the selector)
- [ ] T083 [US8] Change `run_step` in `src/pipe/stepper.py` (T082; depends on T041, T075, T081; same file as T040): after the claim contest, call `bind_step` (tag steps), then `check_input`. A failure ends the step with `invalid_payload` and posts the failure (T053). Then, for a `write` step, the gate (004). Then `build_run_request(step, starter, owner, cap.output_schema)` and `RuntimePort.run` (the selector). After the run, call `check_output`. A failure ends the step with `invalid_result`

**Checkpoint**: User Stories 7 and 8 work.

---

## Phase 8C: Second batch of owner decisions (2026-11-26, constitution 1.3.0)

**Purpose**: Plan source and hop limit, dialog step, context, plan proposal and gate, exclusion, failure branch, `flow:` word, new message types, and the rejected `write` tag step. The decisions are N1 to N13 in [plan.md](plan.md). The stories are US9 to US12 in [spec.md](spec.md). Spec 006 builds on these tasks. Spec 006 supplies `Flow`, `expand_flow`, and `parse_flow_mention`. Until spec 006 exists, the tests use `FakeFlow` (fields `hash`, method `matches(steps, cards, starter)`) and a stub `expand`.

**Independent Test**: Run `pytest tests/unit/test_source.py tests/unit/test_route_dialog.py tests/unit/test_route_gate.py tests/unit/test_exclusion.py tests/unit/test_branch.py tests/unit/test_route_flow.py tests/integration/test_dialog_step.py tests/integration/test_gate_proposal.py tests/integration/test_branch.py`. Then do the quickstart scenarios "9" to "12".

### US12: Plan source and hop limit by source (Priority: P1)

- [ ] T090 [P] [US12] Write failing test for `parse_source`, `hop_limit`, and `effective_source` in `tests/unit/test_source.py` (FR-042, SC-023, decision N7). `FakeFlow` has `hash` and `matches(steps, cards, starter)`:
  - `hop_limit("free")` is 3. `hop_limit("template")` is 5. The constants are `MAX_HOP_FREE = 3` and `MAX_HOP_TEMPLATE = 5`. No fixed `MAX_HOP` exists.
  - `parse_source("template:bugfix@<32 hex>")` gives `("bugfix", hash)`. `"free"`, `None`, `""`, `"template:"`, `"template:Bug@abc"`, a hash of 31 or 33 characters, and a hash with upper case give `None`.
  - `effective_source(plan, flows, cards, starter)` gives `template` only when all hold: the source parses, `flows` has the name, `flows[name].hash` equals the hash, and `flows[name].matches(plan.steps, cards, starter)` is true.
  - It gives `free` for: a missing source, `free`, an unknown name, a different hash, `matches` false (a changed step), and empty or `None` `flows`. It never raises, also for a hostile source string.
  - The function does not change its input. The module imports no file, no chat, no runtime module, and names no tag.
- [ ] T091 [US12] Implement `src/pipe/core/source.py` (T090): `MAX_HOP_FREE`, `MAX_HOP_TEMPLATE`, `parse_source`, `hop_limit`, `effective_source`
- [ ] T092 [P] [US12] Write failing test for the limit by source in `tests/unit/test_validate_plan_source.py` and `tests/unit/test_route_source.py` (FR-004, FR-009, FR-042, SC-023, SC-004):
  - `validate_plan(plan, cards, starter, flows)` accepts 4 bot steps when the effective source is `template` (Fake flow that matches), and 5. It rejects 6. It rejects 4 bot steps for a `free` plan and for a declared template that is not verified (hash differs, name unknown, steps differ, `flows` empty). The error is `plan has N agent steps, the limit is M`.
  - `validate_plan` called with no `flows` argument behaves as for a `free` plan (limit 3).
  - A `source` string with a bad form (from a hand-made plan) gives the error `bad source`.
  - `route` with a verified template: a handoff with `hop` 4 and `hop` 5 gives `claim`. `hop` 6 gives `refuse`.
  - `route` with a declared template that is not verified: `hop` 4 gives `refuse`. The refusal reason ends with ` (plan source not verified)`. The same handoff for a `free` plan gives the plain reason `hop limit exceeded`.
  - Two adapters with different `flows` (one with the matching hash, one with another hash): the first claims at `hop` 4, the second refuses (spec 006 DQ10 = a, fail closed).
  - A forged plan message from a bot with a card, with a template source and 5 other steps: the effective source is `free` and the limit is 3.
- [ ] T093 [US12] Implement the limit by source in `src/pipe/core/pipeline.py` (`validate_plan(plan, cards, starter=None, flows=None)`, rules 1 and 17, `parse_task` accepts `pipeline.source`), in `src/pipe/core/route.py` (the `hop` check and the refusal reason), in `src/pipe/core/render.py` (the text `Stopped. Reason: hop limit exceeded (plan source not verified)`), and add `ThreadState.flows` (T092; depends on T091; same files as T021, T030)

### US9: Dialog step (Priority: P2)

- [ ] T094 [P] [US9] Write failing test for the pure dialog rules in `tests/unit/test_route_dialog.py` (FR-036, FR-045, SC-018, data-model.md route rules 1, 4, 5):
  - `open_question(thread)` gives the latest trusted type 10 message with `status: waiting` that has no later message for its step. It gives `None` after a resume (`running`), after `failed`, and when a later `done` exists.
  - `dialog_expired(question_ts, now, hours)` is false at 23 h 59 min and true at 24 h 1 min for `hours` 24.
  - `HumanMessage` thread reply, open question by this agent, the reply mentions this agent: from the thread starter gives `resume`. From the card owner of this agent gives `resume`. From another person gives `chat` (the question stays open). A reply with no mention is not an event.
  - A reply for a question of another agent gives `ignore(not_for_me)`.
  - A second reply after the resume (no open question) gives `chat`.
  - `Wake` with an expired own question gives `expire_dialog`. A question that is not expired gives `ignore`. A `waiting` question is NOT interrupted (`interrupt` needs `step_status` `claimed` or `running`).
  - `check_task_msg` accepts a type 10 message `by` the step agent (`waiting`, `needs_input`) and ignores one by another agent (`not_assigned`) or by a bot with no card (`no_card`).
  - `step_status` of a step is `waiting` while the question is open. `thread_status` is `waiting`.
  - No function reads a tag or a capability name.
- [ ] T095 [US9] Implement `open_question`, `dialog_expired`, the `resume` and `expire_dialog` actions in `src/pipe/core/route.py` and `src/pipe/core/pipeline.py`, and the type 10 checks in `src/pipe/core/trust.py` (T094; depends on T112, T113; same files as T022, T030, T052)
- [ ] T096 [US9] Write failing test for the config key `dialog_timeout_h` in `tests/unit/test_config.py` (same file as T005, so it is not parallel with T005; FR-036): default 24. A value of 0, a negative value, 169, a float, and a string are errors. 1 and 168 are accepted
- [ ] T097 [US9] Implement the validation of `dialog_timeout_h` in `src/pipe/config.py` (T096; same file as T006)
- [ ] T098 [P] [US9] Write failing test in `tests/integration/test_dialog_step.py` with `FakeTransport`, `FakeRuntime`, `FakeTimers`, and the fake clock (FR-036, SC-018, US9 scenarios 1 to 6):
  - `FakeRuntime` returns `waiting`, `needs_input`, and the text "Which branch?" for the first call, and `done` for the second call. The thread shows one type 10 message (`waiting`) that mentions the thread starter and tells the person to mention the agent. No `next` handoff goes out.
  - A reply from the thread starter that mentions the agent: the type 10 message goes to `running`. `FakeRuntime` gets the second call with the same `task` (same `step`, same `payload`), the same `RunRequest`, and a thread that holds the question and the answer. The thread has exactly ONE claim message for the step. `hop` of every later message is unchanged. The result is type 5 `done`.
  - A reply from the agent owner gives the same result. A reply from another person gives no run. The question stays open.
  - 3 hours pass with `step_timeout_min` 30: no `timeout` message (the step timer counts only runs).
  - 24 hours and 1 minute pass (`FakeTimers.fire_all()`): the question message is `failed`, `reason: dialog_timeout`, with a "Retry" button. No run starts alone. "Retry" by the thread starter gives a new claim for the same step with the same `hop`.
  - The adapter restarts during the wait (`Wake`): no `interrupted` message. After the limit, `Wake` gives the `dialog_timeout` failure once.
  - A second answer after the resume gives no second resume.
- [ ] T099 [US9] Implement the dialog in `src/pipe/stepper.py` and `src/pipe/adapter.py` (T098; depends on T040, T041, T095, T097): `ask_question` (post type 10, start the dialog timer with the injected factory), `resume_step` (update type 10 to `running`, run the SAME step with the same request and task, no claim, no `hop` change), `expire_dialog` (update type 10 to `failed` with `dialog_timeout` and the `pipe_retry` button), the in-flight key `resume:<channel>:<ts>`, and the route wiring of `resume` and `expire_dialog`. The dialog timer is separate from the step timer

### US10: Context, gate, and plan proposal (Priority: P2)

- [ ] T100 [US10] Write failing test for `effective_payload` in `tests/unit/test_runrequest.py` (same file as T032 and T074, so it is not parallel; FR-037, SC-019, decision N2):
  - No earlier step gives the plan `payload` unchanged (no `context`, no `artifacts` key). A plan `payload` of `None` gives `{}` when there is context, and `{}` when there is none.
  - Two done steps give `context` as `[{step, text, artifacts}, ...]` in step order, and `artifacts` as all links in order with no duplicate.
  - A key that the plan `payload` sets (`artifacts` or `context`) wins.
  - A `text` of 1500 characters is cut to 1000. Six texts of 1000 characters are cut so that all texts together have at most 4000 characters (the later texts are cut first). Links are never cut.
  - A step that is not `done` (failed, branch source) adds no entry.
  - The function does not change its input. The result holds no `hop`, `by`, `owner`, or trust data.
  - `check_input(step, cap)` validates the effective payload: an `input_schema` with `additionalProperties: false` and no `context` key fails for step 1 and passes for step 0 (default U4).
- [ ] T101 [US10] Implement `effective_payload` in `src/pipe/core/runrequest.py` (T100; same file as T036, T075) and use it in `run_step` (`task.payload`) and in `check_input` in `src/pipe/stepper.py` (same file as T040, T083)
- [ ] T102 [P] [US10] Write failing test for the gate and proposal rules in `tests/unit/test_route_gate.py` (FR-038, FR-043, FR-045, SC-020):
  - `gate_pending(thread, i)` is true for a type 5 `needs_approval` of step `i` with no later `done` message of step `i`. It is false after the release message.
  - `Reaction` ✅ by the thread starter on that message, by this adapter: `release`. By the card owner of the planner: `release`. By another person: `ignore(not_allowed)`. On the plan message only (no ✅ on the gate message): `ignore`. A second ✅ after the release: `ignore`. A ✅ on a type 5 message of another agent: `ignore`.
  - `next_step` after a gated step is `None` until the release. `thread_status` is `needs_approval` while `gate_pending`. A gate on the last step ends the thread only after the release.
  - `validate_plan` rules 15: `gate: approval` on a bot step is valid, on a human step is an error, any other value is an error. A free plan may use `gate`.
  - `check_task_msg` accepts a type 5 `needs_approval` `by` the step agent. Its `pipeline` counts as a proposal only when `validate_plan(proposal, cards, starter)` (free, no flows) returns `[]`. Else the message stays a gate with no proposal (`bad_proposal` is logged).
  - A proposal never makes a handoff: `route` gives `ignore` for a type 5 `needs_approval` message that has `next`.
  - The release of a trigger thread: the starter is a bot, so only the card owner of the planner can release.
- [ ] T103 [US10] Implement `gate_pending`, `next_step` (gate part), the `release` action, and the type 5 checks in `src/pipe/core/pipeline.py`, `src/pipe/core/route.py`, and `src/pipe/core/trust.py` (T102; depends on T112, T113)
- [ ] T104 [P] [US10] Write failing test in `tests/integration/test_gate_proposal.py` with `FakeTransport`, two adapters, and `FakeRuntime` (FR-038, FR-043, SC-020, US10 scenarios 1 to 7):
  - Step 0 has `gate: approval` and `FakeRuntime` returns `done`. The thread has a type 5 `needs_approval` message and no handoff. After ✅ by the thread starter, the same adapter posts the `done` message with `next` and the right `hop` once. Two ✅ events (starter and planner owner) give one release. ✅ from another person gives nothing.
  - Step 2 gets `context` with the `text` and `artifacts` of steps 0 and 1 in its payload (`FakeRuntime` records `task.payload`). The `text` of 1500 characters is cut.
  - `FakeRuntime` returns `done` with a `proposal` that passes `validate_plan`: the type 5 message holds the `pipeline`, has `needs_approval`, and no step starts. After ✅ the pipeline goes on with its own steps. The proposal is in the context of the next step (default U2: context only). The thread starts no step from the proposal.
  - A proposal that fails `validate_plan` (unknown agent) gives `failed`, `invalid_proposal`, the errors in the text, and a "Retry" button. No gate message appears.
  - A gate on the last step: the thread is `done` only after ✅.
  - A step never starts work by itself: no run starts between the gate message and the release (`FakeRuntime` call count).
- [ ] T105 [US10] Implement the gate and the proposal in `src/pipe/stepper.py` and `src/pipe/adapter.py` (T104; depends on T041, T101, T103): in `finish_step` post type 5 `needs_approval` for `gate` or a valid `proposal` (no `next`); `release_step` calls the normal `finish_step` path once (in-flight key `release:<channel>:<ts>`); an invalid proposal ends the step with `invalid_proposal`; wire the `reaction_added` route for `release`

### US11: Exclusion and failure branch (Priority: P2)

- [ ] T106 [P] [US11] Write failing test for the exclusion rules in `tests/unit/test_exclusion.py` and `tests/integration/test_exclusion.py` (FR-039, SC-021, decision N4):
  - `claim_excluded(plan, thread, i, agent_id)` is true when step `i` has `exclude_agents_of: [j]` and `step_agent(thread, j)` is `agent_id`. It is false for another agent, for a step with no field, and when step `j` has no agent yet.
  - `route` gives `ignore(excluded)` for a handoff to an agent that holds an excluded step. `check_task_msg` ignores a claim from such an agent (`excluded`). Another eligible agent claims and runs.
  - `validate_plan` rule 13: an index that is not lower than the step index, a human step index, a duplicate, a non-integer, and more than 5 items are errors. The field on a human step is an error.
  - `validate_plan` rule 14 (`exclusion_deadlock`): a fixed step whose agent holds an excluded fixed step is an error. A tag step whose only matching card is the fixed agent of an excluded step is an error. A tag step with an excluded tag step and one eligible card is valid (the holder is unknown at plan time).
  - Run time: agent A wins step 1 (tag step). A is the only agent with the tag of step 2, and step 2 excludes step 1. The step ends `failed`, `no_claimer`, with a "Retry" button, after `step_timeout_min`.
  - The planner prompt tells the LLM to set the field for a step that reviews or checks earlier work (checked in `tests/unit/test_planner_prompt.py`). The core reads no tag.
  - A free plan may use the field (FR-041).
- [ ] T107 [US11] Implement `claim_excluded` in `src/pipe/core/claim.py`, `exclusion_deadlock` and rules 13 and 14 in `src/pipe/core/pipeline.py`, the exclusion check in `src/pipe/core/route.py` and `src/pipe/core/trust.py`, and the prompt line in `src/pipe/planner.py` (T106)
- [ ] T108 [P] [US11] Write failing test for the failure branch in `tests/unit/test_branch.py` and `tests/integration/test_branch.py` (FR-040, FR-041, SC-022, decision N5):
  - `branch_target(plan, i, "run_failed")` gives `plan.steps[i].on_fail`. It gives `None` for `timeout`, `no_claimer`, `invalid_payload`, `invalid_result`, `invalid_proposal`, `dialog_timeout`, `rejected`, `interrupted`, `capability not available`, `hop limit exceeded`, and for a step with no `on_fail`.
  - `next_step` after the step before the branch step ended `done` gives `None` (the branch is skipped). After a type 11 message it gives the branch target.
  - `validate_plan` rule 16: two steps with `on_fail`, a target that is not the last step, the last step with `on_fail`, the step with `on_fail` as the last step, a human step in the plan, a target that is a human step, and a target that is not higher than the step are errors. One valid `on_fail` is valid. A free plan may use `on_fail` and `gate` and `exclude_agents_of` together (FR-041) with the limit 3.
  - `check_task_msg` accepts a type 11 message `by` the step agent with `reason: run_failed` and `next.payload.step` equal to `on_fail`. It ignores one with another reason or target (`bad_branch`), by another agent, and a second one (`already_branched`).
  - `FakeRuntime` returns `status: failed` for step 0: one type 11 message is posted (`failed`, `run_failed`, `hop + 1`, `next` for the branch step). The claim message has no "Retry" button. The branch step runs once with the payload of the effective payload rules. The thread is `done` when the branch step is `done` and `failed` when it fails. No further step starts.
  - `FakeRuntime` returns `done` for step 0: the branch step never starts and the thread is `done`.
  - `RuntimeFailed("timeout")` for step 0: the step is `failed`, `timeout`, with a "Retry" button and no type 11 message. The same holds for `no_claimer`, `invalid_payload`, `invalid_result`, `dialog_timeout`, and `RuntimeFailed("exit 1")`.
  - A "Retry" click on a step that has a type 11 message gives `ignore(already_branched)`.
  - `thread_status` ignores a branched step when it picks the current step.
- [ ] T109 [US11] Implement `branch_target`, `next_step`, rule 16, the type 11 checks, and `branched` in `src/pipe/core/pipeline.py`, `src/pipe/core/route.py`, and `src/pipe/core/trust.py`, and `branch_step` in `src/pipe/stepper.py` (T108; depends on T041, T053, T112, T113). The failure path of T053 posts type 11 for `run_failed` when the plan step has `on_fail`

### US12: `flow:` word and planner `flow` (Priority: P1)

- [ ] T110 [P] [US12] Write failing test for the `flow:` word in `tests/unit/test_route_flow.py`, `tests/unit/test_planner_flow.py`, and `tests/integration/test_plan_flow_word.py` (FR-002, FR-021, FR-044, SC-024, decisions N8, N9, N10):
  - `flow_word("@a add X flow:bugfix now")` is `bugfix`. `flow_word("noflow:x")`, `flow_word("flow:Bad")`, `flow_word("flow:")`, a name of 33 characters, and `flow_word("flow:x_y")` are `None`. Only the first word counts. The word must end at a space or at the end of the text.
  - A top-level message with one agent mention and `flow:bugfix`: `plan_flow` (arg `bugfix`) for that agent. With two agent mentions and `flow:`: `plan_flow` for the first, `ignore(not_planner)` for the second. A message with one agent and no `flow:` word is still `chat`. A thread reply with a `flow:` word is `chat`.
  - The planner for `plan_flow` calls no runtime (`FakeRuntime` call count is 0). It calls the injected `expand` with the template name, then `validate_plan`. A rejected plan gives a type 2 message. A valid plan gives a type 1 message with `pipeline.source` set by the planner core.
  - The planner LLM path: the prompt lists each template as `name` and `description` only. An output with `flow` and `steps` uses the template and ignores `steps`. An unknown `flow` name gives `could not build a plan (unknown flow)`. An output with `steps` and no `flow` gives a plan with `source: free`. The plan schema has no `source` property.
  - The text "save this plan as a flow" gives a normal chat reply. No file appears under `~/.pipe/` or in a `flows` directory (FR-021, principle I). A test fixture that records every file write of the process finds none.
- [ ] T111 [US12] Implement `flow_word` and the `plan_flow` branch in `src/pipe/core/route.py`, the `flow` output and the template list in `src/pipe/planner.py` (with the injected `expand`), and the `flow` property in the plan schema (T110; depends on T093; same files as T022, T024)

### New message types, texts, and parse (all decisions)

- [ ] T112 [US9] Write failing test for `parse_task` and `render_task` of the new shapes in `tests/unit/test_pipeline.py` and `tests/unit/test_render.py` (same files as T003 and T011, so it is not parallel with them; FR-045, contracts/task-metadata.md):
  - `parse_task` accepts a type 5 with `status: needs_approval` and a `pipeline`. It accepts a type 10 (`waiting`, `reason: needs_input`) and a type 11 (`failed` with `next`). It rejects a `pipeline` on a step message that is not `needs_approval`, a `next` on a `failed` message whose `reason` is not `run_failed`, and a `source` string that is not `free` or `template:<name>@<32 hex>`.
  - `parse_task` accepts a plan step with `exclude_agents_of` (list of integers), `gate: approval`, and `on_fail` (integer). It rejects other types and values.
  - `render_task` gives the texts of the contract for the new types ("waiting for input", "needs approval", "failed. Reason: dialog_timeout", the branch line, and the unverified-source refusal). Every text passes `scrub` and `escape_mentions`. The question text mentions the thread starter with the injected `Formatter`. Only the mention of the starter and of the next agents is real.
  - A `reason` is cut to 200 characters. No text holds a path or a URL other than `artifacts`.
- [ ] T113 [US9] Implement the new shapes in `parse_task` (`src/pipe/core/pipeline.py`) and the new texts in `src/pipe/core/render.py` (T112; same files as T004, T012). Update the `Step`, `Pipeline`, and `TaskMsg` dataclasses (`exclude_agents_of`, `gate`, `on_fail`, `source`)

### Rejected `write` tag step (decision N13)

- [ ] T114 [US7] Write failing test in `tests/unit/test_route_tags.py` (same file as T086; not parallel with T086) and `tests/integration/test_tag_reject.py` (FR-046, SC-026; spec 004 owns the gate, so the integration test uses `FakeGate` from spec 004 T052):
  - A `write` tag step with two eligible agents. A wins the claim and its owner rejects it. The step is `failed`, `reason: rejected`, with no "Retry" button.
  - `step_rejected(thread, i)` is true when the latest claim of step `i` is `failed` with `reason: rejected`.
  - B (the other eligible agent) gets no `claim` from `route`: not for the original handoff, not for a `Wake` pass after its restart. The decision is `ignore(rejected)`.
  - A "Retry" click on the rejected message gives `ignore`. `resolve_claim` is unchanged (rule 1 still drops `failed` claims for other uses).
- [ ] T115 [US7] Implement `step_rejected` in `src/pipe/core/pipeline.py` and the `ignore(rejected)` checks in `src/pipe/core/route.py` (the `BotMessage` and `Wake` branches) (T114; same files as T085, T087)

**Checkpoint**: The second batch works. The brief M5 (spec 006) can build on it.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T064 Write failing test in `tests/unit/test_core_purity.py` (SC-008, principle VII): every module in `src/pipe/core/` imports no `slack_sdk`, `slack_bolt`, `subprocess`, `urllib`, `socket`, `threading`, or `requests`, and calls no `open` for writing. Run it against the new and the old `core/` modules
- [ ] T065 Run `pytest tests/unit tests/integration` and fix failures (quickstart section 1)
- [ ] T066 [P] Check that no file under `src/`, `tests/`, and `~/.pipe/` holds a plain token (Slack or GitLab), and that `mr_state.gitlab.token` in the sample config is a `keychain:` reference (constitution; research.md D17)
- [ ] T067 Check assumptions A3 and A7 against a real `claude` run (research.md "Cannot verify"): a foreign-started `read` step has no file tool; the exposed capability runs; `git push` is denied by `Bash(git push:*)`; `ls ~/.pipe/run` is empty after a run, a failure, and a timeout. Fix `src/pipe/runtime_claude_request.py` if the rule syntax differs
- [ ] T068 Check assumptions A1, A2, A4, and A5 on a real Slack workspace (research.md "Cannot verify"): `app_mention` for a bot-posted handoff (else add the `message.channels` fallback in `src/pipe/adapter.py`); metadata and reactions in `conversations.replies`; `block_actions` payload fields; metadata size; `chat.delete` of the own message
- [ ] T069 Check assumption A6 and the metrics script with a real merged MR and the read-only GitLab token (quickstart section 3). Compare the output with the thread contents by hand. Fix `src/pipe/gitlab_io.py` if the response shape differs
- [ ] T070 Run the manual scenarios of `quickstart.md` section 2 on a real Slack workspace with two adapters. Time the hung step (SC-006). Read one finished thread alone and write down the pipeline state (SC-007)

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependency.
- Foundational (Phase 2): needs Phase 1. It blocks all user stories.
- US1 (Phase 3): needs Phase 2.
- US3 (Phase 4): needs Phase 3 (T022, T021). It runs before US2 because the guard protects every handoff.
- US2 (Phase 5): needs Phase 4 (T031) and Phase 3. T073 needs T036 and the 002 load-set tasks (T022 to T024 of spec 002).
- US4 (Phase 6): needs Phase 5 (T041).
- US5 (Phase 7): needs Phase 6 (T047) and Phase 5. T055 and T056 need T052.
- US7 (Phase 8A): needs Phase 7 (T047, T057) and Phase 2. T085 is in `pipeline.py`. T089 needs 002 T061 (card `access` and `tags`) and T040 to T041.
- US8 (Phase 8B): needs Phase 5 (T040, T041, T073) and spec 002 Phase 5A (T055, T057, T059). T083 needs T075 and T081.
- US6 (Phase 8): needs Phase 2 (T014). It does not need Phases 3 to 7 for its pure tests (T058 to T062). T063 needs T014.
- Phase 8C (second batch): needs Phases 3 to 5 and 8A. T112 and T113 (new shapes) come first. Then T090 to T093 (source), T094 to T099 (dialog), T100 to T105 (context, gate, proposal), T106 to T109 (exclusion, branch), T110, T111 (flow word), T114, T115 (rejected). T099, T105, and T109 need `stepper.py` tasks T040, T041, T053. T111 needs the spec 006 `expand_flow` or its stub.
- Polish (Phase 9): needs all stories.

### Within Each User Story

- Test tasks come first and MUST fail before the implementation task.
- Pure functions in `src/pipe/core/` before the I/O code that calls them.
- Tasks that edit the same file are not marked [P]: `pipeline.py` (T004, T021, T030, T037), `route.py` (T022, T030, T038, T052), `stepper.py` (T025, T031, T039 to T042, T047, T053, T054, T057), `runtime_claude.py` (T023, T073), `adapter.py` (T026, T031, T043, T055, T056).
- IDs T074 to T089 were added on 2026-11-26 (declared capabilities and late binding). They sit in Phase 8A and Phase 8B, in file order. IDs T071 to T073 were added after the first numbering. T071 sits in Phase 2 and T072 and T073 sit in Phase 5, in file order.
- Test-first pairs (second batch): T090 before T091. T092 before T093. T094 before T095. T096 before T097. T098 before T099. T100 before T101. T102 before T103. T104 before T105. T106 before T107. T108 before T109. T110 before T111. T112 before T113. T114 before T115. T090 and T092 before T093.
- Test-first pairs: T074 before T075. T076 before T077. T078 before T079. T080 before T081. T082 before T083. T084 before T085. T086 before T087. T088 before T089. T003 before T004. T005 before T006. T007 before T008. T011 before T012. T013 before T014. T016 before T021. T017 and T018 before T022. T019 before T023. T020 before T024 to T026. T027 and T028 before T030. T029 before T031. T032 before T036. T072 before T073. T033 before T037. T034 before T038. T035 before T039 to T043. T044 before T046. T045 before T047. T048 before T052. T049 before T055. T050 before T053, T054, T056, T057. T051 before T055. T058 before T061. T059 before T062. T060 before T063. T064 before Phase 9 runs. T071 runs with every core task: it fails until the core files exist and must pass after each core task and in T065.

### Parallel Opportunities

- Phase 2: T003, T005, T007, T009, T011, T013, T071 together. T010 beside T011 after T004 and T009.
- US1 tests T016 to T020 together; then T023 beside T021.
- US3 tests T027 to T029 together.
- US2 tests T032 to T035 and T072 together; T036 beside T037 and T038; T073 after T036.
- US4 tests T044 and T045 together.
- US5 tests T048 to T051 together.
- US6 can run beside US2 to US5 with another developer after Phase 2: T058 to T062 together.

---

## Parallel Example: User Story 1

```text
# Launch all tests together:
Task: "Write failing test for validate_plan in tests/unit/test_validate_plan.py"
Task: "Write failing test for the HumanMessage branch of route in tests/unit/test_route_human.py"
Task: "Write failing test for the Reaction branch of route in tests/unit/test_route_reaction.py"
Task: "Write failing test for the planner command in tests/unit/test_runtime_claude.py"

# Then the implementation in order (same files):
Task: "Implement validate_plan and find_plan in src/pipe/core/pipeline.py"
Task: "Implement mentions, first_agent, and the HumanMessage and Reaction branches of route in src/pipe/core/route.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1, 3, and 2)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1): a plan with ✅.
3. Complete Phase 4 (US3): the trust and hop guard.
4. Complete Phase 5 (US2): the steps run one by one. Stop and validate: tests pass, then quickstart scenarios "1", "2", "3".

### Incremental Delivery

1. Add US4 (claims). Validate.
2. Add US5 (timeout, retry, offline wait, catch-up). Validate. This gives the full M2 acceptance of the design brief, except the metrics script.
3. Add US6 (metrics). Validate with the test channel.
4. Polish: manual checks on real `claude`, real Slack, and real GitLab.

### Traceability

- FR-001: T017, T022, T027, T030. FR-002: T017, T022. FR-003: T020, T024. FR-004: T016, T020, T021, T024. FR-005: T020, T024. FR-006: T018, T020, T022, T025. FR-007: T018, T034, T038, T048, T052. FR-008: T007, T008, T027, T029, T030. FR-009: T027, T028, T029, T030, T031. FR-010: T028, T030. FR-011: T033, T035, T037. FR-012: T011, T012, T033, T035, T037, T041. FR-013: T034, T035, T038, T041, T042. FR-014: T044, T045, T046, T047. FR-015: T050, T053, T054. FR-016: T050, T053. FR-017: T048, T050, T057, T058. FR-018: T017, T051, T055. FR-019: T048, T049, T051, T055, T056. FR-020: T003, T004. FR-021: T020. FR-022: T032, T035, T036, T040, T072, T073. FR-023: T058, T059, T060, T061, T062, T063. FR-024: T071, T036, T064. FR-025: T016, T021, T032, T036. FR-026: T007, T009, T010, T013, T014, T020, T025. FR-027: T032, T036, T072, T073. FR-028: T084, T085, T088. FR-029: T084, T085. FR-030: T086, T087, T088, T089. FR-031: T088, T089. FR-032: T074, T075, T082, T083. FR-033: T074, T075, T082, T083. FR-034: T074 to T083. FR-035: T007, T008, T053 to T056 of spec 001.
- SC-001: T016, T020. SC-002: T018, T020. SC-003: T007, T027, T029. SC-004: T027, T028, T029. SC-005: T044, T045. SC-006: T050, T070. SC-007: T011, T035, T070. SC-008: T064 and every unit test task. SC-009: T032, T035, T072. SC-011: T071. SC-012: T010, T020. SC-013: T084, T088. SC-014: T086, T088. SC-015: T088. SC-016: T074, T082. SC-017: T076, T078, T082. SC-010: T058, T060, T069.
- Second batch (2026-11-26): FR-036: T094, T096, T098. FR-037: T100, T104. FR-038: T102, T104. FR-039: T106. FR-040: T108. FR-041: T106, T108. FR-042: T090, T092. FR-043: T102, T104. FR-044: T110. FR-045: T094, T102, T108, T112. FR-046: T114. FR-002 and FR-021 (changed): T110. FR-004, FR-009, FR-010 (changed): T016, T027, T028, T092. SC-018: T098. SC-019: T100, T104. SC-020: T102, T104. SC-021: T106. SC-022: T108. SC-023: T090, T092. SC-024: T110. SC-025: T071. SC-026: T114.
- Design brief §9 M2 acceptance: plan with unknown agent or hidden capability (T016, T020). ✅ from another person (T018, T020). Metadata from a bot with no card (T007, T029). `hop` 4 (T027, T029). Two claims (T044, T045). Hung step (T050). Step started by another person: exposed capabilities only and no file tool (T032, T035, T072). Metrics script (T058 to T060).
- Spec 002 reuse: card format and `validate_card` (T007, T008). Load set from capability IDs, built by the `claude` adapter (T072, T073). Design decisions: N1 to N13 (see the second-batch line above and plan.md), Q1 (T017, T022, T110), Q2 (T016, T028, T030), Q3 (T016, T034, T042), Q4 (T048, T052, T056), Q5 (T032, T036, T072, T073), Q6 (T036, T040), Q7 (T009, T010, T013, T014, T015), Q8 (T058, T061).

---

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Verify that each test fails before you write the implementation.
- Do not commit from these tasks without an explicit owner request.
- If the owner changes a design decision, change the tasks listed for that decision in the Traceability section.
