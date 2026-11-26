---

description: "Task list for Review Capability and External Triggers"
---

# Tasks: Review Capability and External Triggers

**Input**: Design documents from `/specs/005-review-gitlab-triggers/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md. Specs 001 to 004 are implemented, with the second batch of spec 003 (constitution 1.3.0): late binding by tag (003 T084, T085), `effective_payload(step_payload, results)` (003 T100, T101), `check_input` (003 T075), `exclude_agents_of` (003 T106, T107), `on_fail` (003 T108, T109), `plan_flow` and `flow_word` (003 T110, T111), the `Transport` port and `upload_file` (001 T059, T060), and the config-declared capabilities of 002.

**Tests**: Tests are required. Constitution principle VII (NON-NEGOTIABLE): every pure-function business rule has a test task BEFORE its implementation task. The test must fail first. Tests use fakes: no real Slack, no real GitLab, no real wiz-review, no real Claude, no network.

**Organization**: Tasks are grouped by user story. Paths follow the Source Code layout in [plan.md](plan.md). The tasks follow the owner decisions in "Design decisions" of plan.md (DQ1 to DQ9) and the recommendation for the open question O1, and constitution v1.3.0 principle XI (the core is capability-agnostic). If the owner changes a decision, change the tasks that plan.md lists for it.

**Changes to 001 to 004 files**: 005 changes code and tests that 003 and 004 made. Each such task says "change" and names the earlier task. 005 does not change the specs of 001 to 004. Plan.md lists the spec changes that another agent must make.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US3, from [spec.md](spec.md)
- Test tasks start with "Write failing test" or "Change the test".
- In Phase 5, the test tasks come first (T016 to T026, even numbers). The implementation tasks follow (T017 to T027, odd numbers, and T028). T036 and T037 (file upload) were added in pass 2 and sit in Phase 4.

## Path Conventions

Single project: `src/pipe/`, `tests/unit/`, `tests/integration/`, `tests/fakes.py` at the repository root (same as 001 to 004). Templates sit in `templates/` outside the package.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the files. Check the baseline.

- [ ] T001 Create the empty new files from the plan: `src/pipe/core/trigger.py`, `templates/trigger/post_trigger.py`, `templates/trigger/gitlab-ci.yml`, `templates/review/wiz_review_capability.py`, `templates/review/config.example.yaml`
- [ ] T002 Run `pytest tests/unit tests/integration` for specs 001 to 004. All tests must pass before 005 work starts. The model changes that 005 uses all exist in 001 to 004 (see Prerequisites), so this task is not a stopper. Do not add a Python dependency. Open item: the optional `exec` output field `files` (plan.md O1) is new in 005 (T036, T037)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The boundary test, the fakes, and the claimant rule. Every story needs them.

**CRITICAL**: No user story work starts before this phase is complete.

- [ ] T003 [P] Change the import-boundary test in `tests/unit/test_core_boundary.py` (003 T071, 004 T017; FR-022, SC-004, principle XI). Write failing cases:
  - The list of core modules gets `trigger.py`. The test first checks that `src/pipe/core/trigger.py` exists (T001). The glob covers every module of `src/pipe/core/` (003 T071; `gate.py` of 004, `source.py` of 003, and `flows.py` of 006 included).
  - The list of forbidden terms gets `wiz`, `gitlab`, and `review`. A term matches a whole word inside an identifier or a string constant (split on `_`, `-`, and non-letters). Comments and docstrings are not read.
  - The list of forbidden imports gets any import of a module under `templates`.
  - The negative case stays. Add a second negative case: a temporary core module with the string constant `"wiz-review"` makes the checker report an error.
  - Check by hand that the existing core modules hold none of the new terms. A hit is a finding to fix in that module, not in the test.
- [ ] T004 [P] Extend `tests/fakes.py` (FR-004, FR-007, FR-013):
  - `FakeRuntime` gets `hold(step)` and `release(step, output)`: a run for that step does not return until `release`. A second `release` is a no-op. It also records each run request.
  - `make_card(kind="trigger", skills=[])` builds a trigger card with `mode: ci`.
  - `make_trigger_message(bot_id, agent_user_id, pipeline=None, flow=None, goal=None, hop=0, thread_ts=None)` builds a top-level `BotMessage` with the payload of [contracts/trigger-message.md](contracts/trigger-message.md): form A (a `pipeline`) or form B (the text `flow:<name> <goal>`, no `pipeline`). A call with both or with neither builds the bad cases.
  - A helper `make_review_cards(...)` builds a reviewer card with a capability that has the tag `review`.
  - `FakeTransport` gets no new method (the `Transport` port stays as it is; `upload_file` exists from 001 T060).
- [ ] T005 [P] Change the test of `route` and `step_status` in `tests/unit/test_route_bot.py` and `tests/unit/test_pipeline.py` (003 T027; FR-006, FR-008, SC-002, research.md D3). Write failing cases. If a case passes at once, 003 already holds the rule: keep the case and remove T006:
  - Two handoffs for step 1 from the same bot: the earlier one gives `claim`. The later one gives `ignore(duplicate_handoff)`.
  - A second `done` message of step 1 changes neither `step_status` nor `thread_status`. It starts no second next step.
  - A handoff for step 2 from a bot that does not hold the winning claim of step 1 gives `ignore(not_claimant)`, also when that bot has a card.
  - A `done` message for step 1 from a bot that does not hold the winning claim gives no `done` in `step_status`.
  - A handoff from the winning claimant gives `claim` (no regression).
  - The functions do not change their input.
- [ ] T006 Implement the claimant rule and the first-handoff rule in `src/pipe/core/route.py` and `src/pipe/core/pipeline.py` (T005; same files as 003 T022 and T004)

**Checkpoint**: Foundation ready. User stories can start.

---

## Phase 3: User Story 1 - Review step in a pipeline (Priority: P1) MVP

**Goal**: A step with `capability: "tag:review"` runs on a reviewer agent. The next step starts after `status: done`. The core has no review code.

**Independent Test**: Run `pytest tests/unit/test_runrequest.py tests/integration/test_review_step.py`. Then do the quickstart scenarios "1".

### Tests for User Story 1 (write first, they MUST fail)

- [ ] T007 [P] [US1] Write failing test for the review `input_schema` against the effective payload in `tests/unit/test_review_input_schema.py` (FR-005, FR-011, research.md D4, D5, DQ2). The function `effective_payload(step_payload, results)` and `check_input` are spec 003 code (T101, T075). This test only uses them. Load the `input_schema` of `templates/review/config.example.yaml`:
  - `results` with one done step `{step: 0, text: "made MR", artifacts: ["https://x/1"]}` and an empty plan payload give `check_input` = `None` (the `artifacts` key has the link).
  - A plan payload `{"mr_url": "https://x/2"}` with no results gives `None`.
  - No link anywhere gives `invalid_payload`.
  - The schema has `additionalProperties: false` and lists `mr_url`, `context`, and `artifacts`. A payload with the keys `context` and `artifacts` that 003 adds is valid. A payload with an unknown key is not.
  - Two done steps give both texts in `context`. A link in the step 0 `artifacts` reaches a review at step 2.
  - Values are opaque: a string with the word `review` passes through unchanged.
- [ ] T008 [P] [US1] Write failing test in `tests/integration/test_review_step.py` with two adapters, `FakeTransport`, and `FakeRuntime` (FR-001 to FR-005, FR-011, FR-027, SC-001):
  - Cards: `coder` (capability `cap-code`), `reviewer` (capability `cap-wr` with the tag `review` and an `input_schema` that needs `mr_url` or a non-empty `artifacts`).
  - Plan A: step 0 `{agent: coder, capability: cap-code, access: write}` with an MR link in `artifacts`; step 1 `{agent: "any", capability: "tag:review", access: read}`. The plan check passes. The plan has no field `kind`.
  - Step 1 is claimed by `reviewer` (lowest `ts` when two reviewers exist). The run request has `capabilities == ("cap-wr",)` and `access == "read"`. The runtime `task.payload` is the effective payload: it has the MR link under `artifacts` and the `context` of step 0.
  - While `FakeRuntime` holds the run, step 1 is `running` and no handoff for the next step exists. After `release`, step 1 is `done` and the next step starts.
  - Plan B: the same pipeline with `agent: reviewer` and `capability: cap-wr` (fixed). The result is the same.
  - A review step whose payload has no link: the step is `failed`, `reason: invalid_payload`. `FakeRuntime` has no run. A "Retry" button exists.
  - The review step has `exclude_agents_of: [0]` and the coder also has the tag `review`: the coder's claim is ignored (`excluded`, spec 003) and the reviewer wins. This case follows 003 T106 and adds no 005 rule.
  - No agent has the tag `review`: the plan check rejects the plan before ✅.
  - No test asserts a review-specific call in the core (the test uses only the tag as data).

### Implementation for User Story 1

- [ ] T009 [US1] Write the review `input_schema` (a change link as `mr_url` or `artifacts`, `additionalProperties: false`, with `context` and `artifacts` listed) in `templates/review/config.example.yaml` (T007; same file as T011). No core code: `effective_payload` is spec 003 (T101)
- [ ] T010 [US1] Make T008 pass. Check that `src/pipe/stepper.py` (003 T101) passes `effective_payload(step.payload, results)` to the run and to `check_input`, and that a failure posts `failed` with `reason: invalid_payload` and the "Retry" button. Change the stepper only if T008 shows a gap (T008, T009; same file as 003 T101 and 004 T028). Make no review-specific branch
- [ ] T011 [P] [US1] Write `templates/review/config.example.yaml` (FR-002; same file as T009; use the declared-capability format of spec 002): one declared capability for the wrapper (use the declared-capability format of spec 002), the `tags` map entry `[review]`, the `exposed` entry, and a comment about `step_timeout_min`. The file holds no token, no URL, and no local path. Use placeholders such as `<capability_id>`

**Checkpoint**: A review step works with a fake runtime. Run T008 and the quickstart scenarios "1" after T014.

---

## Phase 4: User Story 2 - A slow capability reports completion (Priority: P1)

**Goal**: A slow capability keeps its step `running` until the end. Only the claiming agent can end the step. The wiz-review wrapper sends one request and waits for the drafts.

**Independent Test**: Run `pytest tests/unit/test_wiz_review_capability.py tests/integration/test_async_completion.py`. Then do the quickstart scenarios "2".

### Tests for User Story 2 (write first, they MUST fail)

- [ ] T012 [P] [US2] Write failing test in `tests/integration/test_async_completion.py` with `FakeTransport`, `FakeRuntime` (hold and release), and a fake clock (FR-004, FR-006 to FR-010, SC-002, SC-003, SC-009):
  - A held run keeps the claim `running`. No next handoff exists. The core has no field or flag for "slow".
  - A held run that ends with the runtime result `status: failed` gives `failed`, `reason: run_failed`. With `on_fail` on the plan step, one type 11 message follows and has no button. Without `on_fail`, the claim has a "Retry" button.
  - A held run that ends with `RuntimeFailed("exit 1")` gives `failed` with a "Retry" button and no type 11 message, also when the plan step has `on_fail` (FR-025, SC-015).
  - After `release` with success, the claiming bot posts `done` with `artifacts`, and the next step starts once.
  - A `done` message from another bot with a card, from a bot with no card, and a human message "done" change nothing. The step stays `running`.
  - A second `release` or a second result message for the step starts no second next step.
  - `release` with a `RuntimeFailed` error gives `failed`, a scrubbed reason, and a "Retry" button. A token-like string in the reason becomes `[redacted]`.
  - No release before the time limit: after `step_timeout_min` plus 59 seconds the step is `failed`, `reason: timeout`, with a "Retry" button. The held run is cancelled.
  - "Retry" starts a new claim. The fake external state shows one request for the MR (the fake capability asks its state first).
- [ ] T013 [P] [US2] Write failing test for the wrapper in `tests/unit/test_wiz_review_capability.py` (FR-005, FR-012, research.md D6, contracts/slow-capability.md). Use a fake command runner and a fake `sleep`. Import the file by path:
  - `find_link(payload)` returns `mr_url`, else the first `https://` link of `artifacts`, else `None`. A link with another scheme gives `None`.
  - No link gives exit code 2 and the text `missing change link`. The fake runner has no call.
  - State `none` gives one request, then polls. State `pending` gives no request. State `ready` gives no request and no wait.
  - The loop polls with the interval 15 and returns when the state is `ready`. State `error` gives a non-zero exit code with a scrubbed reason.
  - A second `run` for the same link while the state is `pending` sends no second request (the "Retry" case).
  - The output is one JSON object with `text`, `artifacts`, and optional `status`, `data`, and `files` (FR-024). Every link in `artifacts` starts with `https://`. The review result has no `status` (the default `done`).
  - A `status: failed` result with exit code 0 is a valid output (the e2e case). The test table has one e2e-style case: a failed check prints `{"status": "failed", "text": ...}` and `run` returns exit code 0. A crash returns a non-zero exit code and no `status: failed` object (FR-025).
  - A token-like string in a command output becomes `[redacted]` in the reason and in `text`.
  - The commands come from the environment mapping that the test passes. A missing variable gives a clear error that names the variable and not a value.

### Implementation for User Story 2

- [ ] T014 [US2] Implement the wrapper in `templates/review/wiz_review_capability.py` (T013; standard library only; the output contract is `contracts/slow-capability.md`, so an e2e wrapper copies it). Pure helpers (`find_link`, `next_action`) and one `run(payload, env, runner, sleep)` function. A `main` reads stdin and calls `run`. The step time limit of the adapter ends a wait that does not end (DQ6). No loop limit in the wrapper
- [ ] T015 [US2] Run `pytest tests/unit/test_wiz_review_capability.py tests/integration/test_async_completion.py tests/integration/test_review_step.py` (T008, T012, T013). If T012 fails because the stepper treats the held run as a failure, fix `src/pipe/stepper.py` (same file as T010). Check that the adapter keeps handling other threads while the call waits (DQ9 = a: it does not; the next mention waits for the single runtime slot of 001). Write down the result in the plan "Design questions" DQ9 if the real behavior differs

- [ ] T036 [P] [US2] Write failing test for `upload_run_files` in `tests/unit/test_upload_run_files.py` (FR-026, SC-016, plan.md O1, contracts/slow-capability.md "Files"). Use `FakeTransport` (001 T060) and `tmp_path` as the upload root:
  - A result with `files: [<regular file in the root>]` gives one `upload_file(channel, thread, name, data, title)` call and the returned link appended to `artifacts`. The call uses `data` as a `Path`. The test checks the call record (no content).
  - Two files give two links in order. The existing `artifacts` stay first.
  - A path outside the root, a symbolic link, a directory, a missing file, and a file over 10 MB each give `UploadRefused` from the fake. The step is `failed`, `reason: upload refused`. No other file of that result is sent.
  - A result with no `files` gives no call.
  - `name` is the base name of the path. `title` is the step goal, scrubbed. No path appears in any posted text.
  - The function is outside the core. It imports no chat library.
- [ ] T037 [US2] Implement `upload_run_files` in `src/pipe/stepper.py` (T036; same file as T010, T015, T025; depends on 001 T060). Call it after a result and before the type 5 post. The optional field `files` is parsed by the `exec` adapter (`src/pipe/runtime_exec.py`, 003). If the owner changes O1, change this task and `contracts/slow-capability.md`

**Checkpoint**: US1 and US2 work with fakes. The review path needs no core change beyond T006.

---

## Phase 5: User Story 3 - Start a pipeline from a trigger bot (Priority: P2)

**Goal**: A bot with a `kind: trigger` card starts a pipeline. The allowlist starts it at once. Otherwise the owner gets a button. A trigger bot is never a step agent.

**Independent Test**: Run `pytest tests/unit/test_trigger.py tests/unit/test_route_trigger.py tests/unit/test_post_trigger.py tests/integration/test_trigger_flow.py`. Then do the quickstart scenarios "3".

### Tests for User Story 3 (write first, they MUST fail)

- [ ] T016 [P] [US3] Write failing test for `parse_trigger` and `decide_trigger` in `tests/unit/test_trigger.py` (FR-013, FR-015, FR-018, SC-006, SC-007, research.md D7, D8). Use opaque IDs such as `B1`, `U1`:
  - Form A: a top-level message from `B1` with a card of `kind: trigger`, a valid payload with a `pipeline`, and `flow=None` gives a `Trigger` with `ts`, `sender == B1`, the pipeline, `flow None`, and the title.
  - Form B: no `pipeline`, `flow="nightly"`, and a title (the goal) that is not empty gives a `Trigger` with `flow == "nightly"` and `pipeline None`.
  - `None` for both forms together (a `pipeline` and a `flow`), for neither (no `pipeline`, `flow=None`), and for form B with an empty goal.
  - The payload has no `source`. A `pipeline.source` in the payload does not change the result (the receiver recomputes it).
  - `None` for: no card; card `kind: agent`; `by` different from the message `bot_id`; `hop` 1; `v` 2; `phase: step`; a `next` field; no `pipeline`; a pipeline with a wrong shape; a thread reply; a missing payload.
  - The title is scrubbed, has no mention except escaped ones, and has at most 200 characters.
  - `decide_trigger("B1", ["B1"])` gives `allow`, `allowlisted`. An empty list, a near match (`b1`, `B1 `), `None`, and `""` give `ask`, `not_allowlisted`. A user ID in the list gives `allow` for the same ID only.
  - Both functions do not change their input. `trigger.py` imports only the standard library and 003/004 core modules.
- [ ] T018 [P] [US3] Change the test of `validate_plan` in `tests/unit/test_validate_plan.py` (003 T016; FR-017, SC-008, research.md D10). Write failing cases:
  - A bot step whose agent has a card of `kind: trigger` is an error: `step 1: agent B1 is a trigger bot`.
  - A plan with only `kind: agent` cards stays valid. A step with `agent: "any"` and `capability: "tag:review"` stays valid when one agent card has the tag.
  - A trigger card never counts as a holder of a tag (it has no skills).
- [ ] T020 [P] [US3] Write failing test for the trigger rules of `route` in `tests/unit/test_route_trigger.py` (FR-014 to FR-018, SC-007, SC-010, data-model.md "Route changes"):
  - A valid trigger that names this adapter first gives `trigger`. The route computes `flow_word(text)` (003) and passes it to `parse_trigger`. A form B trigger gives `trigger` with the flow name. A trigger with both forms or neither gives `ignore(bad_payload)`. A trigger that names another agent first gives `ignore(not_planner)`.
  - A trigger from a bot with no card gives `ignore(no_card)`. A top-level `pipeline` message from a `kind: agent` card gives `ignore(not_trigger)`. A bad payload gives `ignore(bad_payload)`. The same `event_id` twice gives one decision.
  - A message from a trigger bot with `next` gives `ignore(trigger_not_agent)`.
  - A click `accept` on the plan message of a trigger thread, by the card owner of this adapter, gives `start`. A click by the thread starter (the trigger bot cannot click), by the sender of the pipeline, or by any other user gives `ignore`. A second click gives `ignore`.
  - A click `reject` by the owner gives `reject_plan`. After it, a "Retry" click gives `ignore`.
  - A click on a plan message of a chat thread (not a trigger) keeps the 003 rules.
  - `Wake` gives `trigger` for an open trigger parent with no plan message by this adapter. It gives nothing when the plan message exists. A plan with `needs_approval` and buttons stays valid after `Wake`.
- [ ] T022 [P] [US3] Change the test of `render_task` in `tests/unit/test_render.py` (003 T011, 004 T015; [contracts/trigger-message.md](contracts/trigger-message.md) "Texts"). Write failing cases:
  - The trigger request text names the trigger bot from the card and has a real `<@U_OWNER>` mention. Every other mention is escaped.
  - The rejected trigger plan text is `failed. Reason: rejected`. The invalid plan text holds the plan errors.
  - A token-like string in a title or a reason becomes `[redacted]`. No text holds a path or a URL.
- [ ] T024 [P] [US3] Write failing test in `tests/integration/test_trigger_flow.py` with two adapters, `FakeTransport`, and `FakeRuntime` (FR-013 to FR-019, SC-005 to SC-008, SC-010, SC-011):
  - Allowlisted trigger: the planner posts a plan message and the start handoff. No ✅. No button. The pipeline runs with a plan of two steps and ends `done`.
  - Not allowlisted: the plan message has Accept and Reject. No handoff exists. The owner clicks Accept: the start handoff appears and the pipeline runs. A non-owner click changes nothing.
  - Reject: the plan message is `failed`, `reason: rejected`. No "Retry". No step runs.
  - The adapter restarts while the buttons show. Accept still works once.
  - Invalid plan (unknown agent, hidden capability, a trigger bot as step agent, four bot steps in a free plan): a plan message `failed` with the errors. No button.
  - Form B (`flow:<name> <goal>`, no `pipeline`): the planner expands the template with the 003 `plan_flow` path (a fake `expand`). `FakeRuntime` has zero planner calls (SC-014). The plan source is the template source. The same gate follows (allowlist: start; else buttons). An unknown flow gives a type 2 message with `could not build a plan (unknown flow)` and no button.
  - Both forms, or neither (a free goal text), start nothing (SC-013).
  - A fixed `pipeline` with a hand-written `source` of a template is treated as `free` when it does not match (the `hop` limit is 3).
  - A trigger with a `write` step for another owner: the delegation gate of spec 004 applies (a button for that owner when the sender is not in its allowlist).
  - The same rules as a chat pipeline: `hop` 4 is refused, two claims give one winner, a held step times out with "Retry".
  - A trigger posted while the planner adapter is down gives a plan after the adapter starts (catch-up).
  - A trigger from a bot with no card, from a `kind: agent` card, and a trigger with `hop` 1 start nothing.
  - The same Slack `event_id` twice gives one thread.
- [ ] T026 [P] [US3] Write failing test for the template in `tests/unit/test_post_trigger.py` (FR-020, FR-023, SC-012, research.md D12). Import `templates/trigger/post_trigger.py` by path. No network:
  - `build_trigger_message(channel, agent_user_id, pipeline, flow, title, bot_id)` gives a dict whose `metadata` passes `parse_trigger` of the core (round trip with a trigger card and `flow_word`). With a `pipeline` (form A) the text is `<@agent_user_id> <title>` and has no `flow:` word. With a `flow` (form B) the text is `<@agent_user_id> flow:<name> <goal>` and the metadata has no `pipeline`. Both together, or neither, raise an error. A form B call with an empty goal raises an error. `hop` is 0. No `task_id`, no `next`, and no `source`.
  - A title with a token-like string, a newline, or `<!channel>` is scrubbed or escaped, and cut to 200 characters.
  - `build_card(name, owner, bot_id, bot_user_id)` passes the core `validate_card` (002 has no `kind` rule, so a `trigger` card passes). `kind` is `trigger`. `skills` is `[]`. `hash` equals the core hash of the empty skills list.
  - `read_token(env)` reads only `PIPE_TRIGGER_TOKEN`. A missing variable gives an error that names the variable and shows no value. No function prints the token. The `Authorization` header is built in one place, and the test checks that no log or exception text holds the token.
  - `post(...)` uses an injected opener. It sends `chat.postMessage` with the metadata, and a Slack error such as `channel_not_found` gives a non-zero exit code and the Slack error name only.
  - The pipeline file is JSON. A file that is not valid JSON gives a clear error. The settings `PIPE_PIPELINE_FILE` and `PIPE_FLOW` together, or neither, give a clear error.

### Implementation for User Story 3

- [ ] T017 [US3] Implement `Trigger`, `parse_trigger(msg, cards, flow)`, and `decide_trigger` in `src/pipe/core/trigger.py` (T016). The module imports only the standard library and core modules. It reuses `in_allowlist` and `Gate` of `src/pipe/core/gate.py` (004)
- [ ] T019 [US3] Change `validate_plan` in `src/pipe/core/pipeline.py` (T018; same file as T006 and 004 T010): add the trigger-agent error
- [ ] T021 [US3] Change `route` in `src/pipe/core/route.py` (T020; same file as T006 and 004 T012): add the actions `trigger` and `reject_plan`, the Accept click on a trigger plan, and the `Wake` rule
- [ ] T023 [US3] Change `render_task` in `src/pipe/core/render.py` (T022; same file as 004 T016): add the trigger texts
- [ ] T025 [US3] Change `src/pipe/stepper.py` and `src/pipe/adapter.py` (T020, T021, T024; same files as T010, 004 T028, and 004 T038). Add `start_trigger` (for form B: expand the template through the 003 `plan_flow` path with no runtime call; validate the plan with `validate_plan(plan, cards, starter, flows)`; post the plan message; then `allow`: post the start handoff, `ask`: add the buttons), `accept_plan` (post the start handoff), and `reject_plan` (update the plan message to `failed`, remove the buttons). The adapter sends top-level bot messages of the work channel to `route`, and handles `pipe_accept` and `pipe_reject` on a plan message. Add in-flight keys `trigger:<channel>:<ts>`. Reuse the 003 start handoff and the 004 click rule. All Slack calls go through the `Transport` port
- [ ] T027 [US3] Implement `templates/trigger/post_trigger.py` (T026; standard library only): `build_trigger_message`, `build_card`, `read_token`, `post`, and a CLI with the commands `card` (post and pin the card) and `post` (post one trigger mention, form A or form B). Settings come from the environment variables in [data-model.md](data-model.md). Never print the token. Scrub the title
- [ ] T028 [P] [US3] Write `templates/trigger/gitlab-ci.yml` (FR-020, FR-023): one job that runs on a schedule or on an event rule and calls `python3 templates/trigger/post_trigger.py post`. It lists the variable names only. A comment says that `PIPE_TRIGGER_TOKEN` must be a masked variable in the GitLab CI settings. It holds no token value, no URL of Slack, and no workspace ID. The job has no `echo` of any variable

**Checkpoint**: All three stories work with fakes. Each story passes its own tests.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T029 Run `pytest tests/unit/test_core_boundary.py tests/unit/test_core_purity.py` (SC-004; 003 T064 and T071, 004 T044). `trigger.py` must hold no I/O import and no forbidden term. Fix the finding in the module, not in the test
- [ ] T030 [P] Check that no new file under `src/`, `tests/`, `templates/`, and `specs/005-review-gitlab-triggers/` holds a token, an MCP URL, or a local path (FR-023, SC-012). Search for `xox`, `xapp`, `glpat`, `Bearer `, and `/Users/` (skip `tasks.md`, which names these strings). Check that `gitlab-ci.yml` and `config.example.yaml` hold placeholders only
- [ ] T031 Check assumption A1 on a real wiz-review (research.md "Cannot verify"): the real request command, the real state command, the state words, and the way the drafts show. Fix `templates/review/wiz_review_capability.py` and `templates/review/config.example.yaml` if they differ. Change no file in the wiz-review repo
- [ ] T032 Check assumptions A2 and A3 with a real trigger bot (`pipe-gitlab`) in a test workspace: the mentioned adapter receives the trigger mention, and the pinned card passes `trusted_cards`. Fix `post_trigger.py` or the 003 trust check report if they differ. Record the Slack scopes in quickstart.md
- [ ] T033 Check assumption A4 with a real GitLab Pipeline schedule: the job reads the masked variable, reaches Slack, and does not print the token in the job log. Measure SC-005 (under 2 minutes from schedule start to the first step message)
- [ ] T034 Run the manual scenarios of `quickstart.md` section 2 on a real Slack workspace with two adapters, a real wiz-review, and a real GitLab project. Measure SC-009 with a short `step_timeout_min`
- [ ] T035 Run `pytest tests/unit tests/integration` and fix failures (quickstart section 1). Then tick the items of `checklists/requirements.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependency.
- Foundational (Phase 2): needs Phase 1. It blocks all user stories.
- US1 (Phase 3): needs Phase 2. T010 needs T008 and T009.
- US2 (Phase 4): needs Phase 3 (T010). T014 needs T013. T015 needs T008, T012, and T013.
- US3 (Phase 5): needs Phase 2. It does not need US1 or US2. T025 needs T017, T019, T021, and T023.
- Polish (Phase 6): needs all stories.

### Within Each User Story

- Test tasks come first and MUST fail before the implementation task.
- Pure functions in `src/pipe/core/` before the I/O code that calls them.
- Tasks that edit the same file are not marked [P]: `route.py` (T006, T021), `pipeline.py` (T006, T019), `stepper.py` (T010, T015, T025), `adapter.py` (T025), `runrequest.py` (T009), `tests/fakes.py` (T004).
- Test-first pairs: T003 runs with every core task and must pass after T017. T005 before T006. T007 before T009. T008 before T010. T036 before T037. T013 before T014. T012 and T013 before T015. T016 before T017. T018 before T019. T020 before T021. T022 before T023. T024 before T025. T026 before T027 and T028.
- T003 changes a 003 and 004 test. It needs `trigger.py` to exist (T001) and fails until then.
- T005 and T006: if 003 already has the rules, T005 passes and T006 is removed.

### Parallel Opportunities

- Phase 2: T003, T004, and T005 together.
- US1 tests T007 and T008 together. T011 beside them.
- US2 tests T012 and T013 together.
- US3 tests T016, T018, T020, T022, T024, and T026 together. T028 beside T027.
- US3 can run beside US1 and US2 with another developer after Phase 2.

---

## Parallel Example: User Story 3

```text
# Launch all tests together:
Task: "Write failing test for parse_trigger and decide_trigger in tests/unit/test_trigger.py"
Task: "Change the test of validate_plan in tests/unit/test_validate_plan.py"
Task: "Write failing test for the trigger rules of route in tests/unit/test_route_trigger.py"
Task: "Change the test of render_task in tests/unit/test_render.py"
Task: "Write failing test in tests/integration/test_trigger_flow.py"
Task: "Write failing test for the template in tests/unit/test_post_trigger.py"

# Then the implementation in order:
Task: "Implement trigger.py in src/pipe/core/trigger.py"
Task: "Change validate_plan, route, and render_task in the core"
Task: "Change stepper.py and adapter.py"
Task: "Implement templates/trigger/post_trigger.py and gitlab-ci.yml"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1) and Phase 4 (US2): a review step runs on a reviewer agent and the next step starts after `done`. Stop and validate: tests pass, then quickstart scenarios "1" and "2".

### Incremental Delivery

1. Add US3 (triggers). Validate. This gives the full M4 acceptance of the design brief.
2. Polish: manual checks on real wiz-review, real Slack, and a real GitLab schedule.

### Traceability

- FR-001: T008. FR-002: T008, T011. FR-003: T008. FR-004: T008, T012. FR-005: T007, T008, T009, T010, T013. FR-006: T005, T006, T012. FR-007: T012, T015. FR-008: T005, T006, T012. FR-009: T012. FR-010: T012, T015. FR-011: T008, T010. FR-012: T012, T013, T014. FR-013: T016, T017, T024, T025. FR-014: T024, T025. FR-015: T016, T017, T020, T021, T024, T025. FR-016: T020, T021, T024, T025. FR-017: T018, T019, T020, T021, T024. FR-018: T016, T017, T020, T021, T024. FR-019: T024. FR-020: T026, T027, T028. FR-021: no task (the feature adds no saved pipeline and no schedule from chat; T030 and the review of the diff check that none exists). FR-022: T003, T029. FR-023: T026, T027, T028, T030. FR-024: T013, T014. FR-025: T012, T013. FR-026: T036, T037. FR-027: T008.
- SC-001: T008. SC-002: T005, T012. SC-003: T012. SC-004: T003, T029. SC-005: T033. SC-006: T016, T024. SC-007: T020, T024. SC-008: T018, T024. SC-009: T012, T034. SC-010: T020, T024. SC-011: T024. SC-012: T026, T030. SC-013: T016, T020, T024. SC-014: T024. SC-015: T012, T013. SC-016: T036.
- Design brief §9 M4 acceptance: a step with the tag `review` starts the review agent and the next step starts after `done` (T008, T012). A bot with a `kind: trigger` card posts a mention and the agent starts the pipeline by allowlist or button (T024). A GitLab schedule posts a mention as one example (T028, T033).
- Design decisions: DQ1 (T012, T013, T014, T015, T036, T037), DQ2 (T007, T008, T009, T010), DQ3 (T016, T017, T020, T021, T024, T025, T026, T027), DQ4 (no task; with option (b) add a count rule to `trigger.py` and a test), DQ5 (no task; quickstart documents it), DQ6 (T012, T014), DQ7 (no task), DQ8 (T008; closed by 003 `exclude_agents_of`), DQ9 (T015). O1 (open): T036, T037.
- Reuse: claim, timeout, "Retry", `Wake`, the start handoff, and the plan check of 003. `in_allowlist` and `Gate` and the buttons of 004. The card shape and `validate_card` of 002. Metrics (003): no 005 task, because a trigger pipeline is a normal pipeline.

---

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Verify that each test fails before you write the implementation.
- Do not commit from these tasks without an explicit owner request.
- If the owner changes a design decision, change the tasks listed for that decision in the Traceability section.
- Pass 2: the `flow:` trigger path needs the 003 `plan_flow` action (T111) and an `expand` function. In tests, a fake `expand` stands in for spec 006.
