# Feature Specification: Review Capability and External Triggers

**Feature Branch**: `005-review-gitlab-triggers`

**Created**: 2026-11-25

**Updated**: 2026-11-26 (pass 2: aligned with constitution v1.3.0, specs 001 to 004, and the second batch of spec 003: context, `exclude_agents_of`, `on_fail`, `plan_flow`, `upload_file`; owner decisions DQ1 to DQ9 confirmed)

**Status**: Draft

**Note on the name**: The directory name `005-review-gitlab-triggers` is historical. The core has no review code and no GitLab code. Review is a capability tag. GitLab CI is the first trigger template.

**Input**: User description: "A pipeline step can ask for a code review. A review step is a normal step whose capability has the tag `review`. wiz-review is the first implementation. When the review agent posts `status: done`, the pipeline continues. Any bot with a `kind: trigger` card can start a pipeline in Slack. A GitLab schedule or event is the first example."

## Model (from specs 001 to 004 and the design brief)

- A step is `{agent, capability, access, goal}` plus optional `target` and `payload`. `access` is `read`, `write`, or `approve`.
- A step can name `capability: "tag:<tag>"` with `agent: "any"`. Any agent whose card has an exposed capability with that tag can claim the step. The claim rule of spec 003 (lowest `ts` wins) picks one agent.
- A step ends when its agent posts `status: done` in the thread. The core has no special callback.
- A card capability can have an optional `input_schema` and `output_schema`. When `input_schema` is present, the step `payload` is checked against it.
- The owner can declare a capability in the config (script, HTTP endpoint, or other CLI). A runtime adapter runs it. The owner can tag it through the config map `tags`.
- A bot with a card of `kind: trigger` has no skills. The allowlist of spec 004 (`in_allowlist`) can name it.
- Slack sits behind the `Transport` port. The core does not import Slack. `Transport.upload_file(channel, thread, name, data, title) -> link` sends a file (scope `files:write`, spec 001 FR-024).
- A step gets the context of all earlier steps: `effective_payload(step_payload, results)` adds `context` (a list of `{step, text, artifacts}`) and `artifacts` (all links) (spec 003 FR-037). `check_input` validates this effective payload.
- A step can have `exclude_agents_of`, `gate: approval`, and `on_fail` (spec 003 FR-039 to FR-041). The planner and the templates set `exclude_agents_of` on a review step.
- A runtime result with `status: failed` gives `reason: run_failed`. A step with `on_fail` then posts a branch handoff (type 11). A `RuntimeFailed` (exit code, http code, timeout) does not branch (spec 003 FR-040).
- `pipeline.source` is `free` or `template:<name>@<32 hex>`. Nobody writes it by hand: the receiver recomputes it with `effective_source` (spec 003 FR-042). The `hop` limit is 3 for a free plan and 5 for a verified template.- The core stays capability-agnostic (principle XI). It knows no review tool, no GitLab, and no CI tool. Review and GitLab are first implementations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review step in a pipeline (Priority: P1)

A pipeline has a review step. The step names `capability: "tag:review"`. An agent that has a capability with the tag `review` claims the step. The agent works. When the agent posts `status: done`, the next step starts. wiz-review is the first implementation behind such a capability.

**Why this priority**: Review handoff is one of the three main goals of the project.

**Independent Test**: Run a pipeline with a `write` step and a review step. Check that a reviewer agent claims the review step, that the next step waits, and that the next step starts after `status: done`.

**Acceptance Scenarios**:

1. **Given** a plan has a step with `capability: "tag:review"`, **When** the plan check runs, **Then** the plan is valid when at least one trusted card lists an exposed capability with the tag `review`. Spec 005 adds no review rule to the plan check.
2. **Given** the review step starts, **When** an agent claims it, **Then** the claim rule of spec 003 picks one agent and the runtime adapter of that agent runs the capability.
3. **Given** an earlier step gave an MR link in `artifacts`, **When** the review step starts, **Then** the review capability receives that link in the effective payload (`artifacts` and `context`, spec 003 FR-037).
4. **Given** the review runs, **When** the reviewer agent has not posted `status: done`, **Then** the next step does not start.
5. **Given** the reviewer agent posts `status: done`, **When** the core reads the thread, **Then** the next step starts.
6. **Given** the plan names a fixed agent and a fixed capability ID for the review step, **When** the step runs, **Then** it behaves in the same way.
7. **Given** the review step has `exclude_agents_of` with the index of the step that made the change, **When** the agent of that earlier step has the tag `review`, **Then** that agent cannot claim the review step (spec 003 FR-039).

---

### User Story 2 - A slow capability reports completion (Priority: P1)

A capability can take a long time and report its end later. A review, an e2e run, and a long test run are examples. wiz-review is the first one: it posts a request, and the drafts come later. The completion reaches the thread only as `status: done` from the claiming agent. No new trust path exists.

**Why this priority**: A review is slow. The pipeline must wait without a new message type and without a new way to trust a message.

**Independent Test**: Run a review step with a capability that ends after a delay. Check that the step stays `running`, that a "done" from another source changes nothing, and that the next step starts after the real end.

**Acceptance Scenarios**:

1. **Given** a claiming agent runs a slow capability, **When** the capability has not ended, **Then** the step stays `running` and the next step does not start.
2. **Given** the capability ends with success, **When** the claiming adapter learns this, **Then** it posts `status: done` with the result in `artifacts`.
3. **Given** the capability ends with an error, **When** the claiming adapter learns this, **Then** it posts `status: failed` with a reason and a "Retry" button.
4. **Given** a message says "done" for the step, **When** it does not come from the claiming agent, **Then** the system ignores it.
5. **Given** the step is `done`, **When** a second "done" arrives for the same step, **Then** the system ignores it and no second next step starts.
6. **Given** the capability does not end within the step time limit, **When** the limit passes, **Then** the step is `failed` with a reason and a "Retry" button.
7. **Given** the wiz-review implementation runs, **When** the step is retried for the same MR, **Then** no second review request is created. The implementation waits for the first one.
8. **Given** an e2e wrapper finds a failed test, **When** it prints `{"status": "failed"}` and exits with code 0, **Then** the step is `failed` with `reason: run_failed`, and a step with `on_fail` posts the branch handoff (type 11).
9. **Given** a wrapper exits with a non-zero code, **When** the adapter reads the result, **Then** the step is `failed` with the exit code as the reason, with a "Retry" button, and no branch handoff.
10. **Given** a wrapper lists a screenshot or a report file in `files`, **When** the step ends, **Then** the adapter uploads each file with `Transport.upload_file` and puts the links in `artifacts`. A file outside `~/.pipe/run/` fails the step with `upload refused`.

---

### User Story 3 - Start a pipeline from a trigger bot (Priority: P2)

A CI job (for example a GitLab schedule or event) posts a mention in `#pipe-work`. It posts as a bot that has a `kind: trigger` card. The mention carries EITHER a fixed `pipeline` in the metadata OR the word `flow:<name>` with a goal in the text (DQ3). A free goal text with no flow word is not allowed. The mentioned agent checks the plan. If the trigger bot is in the allowlist of that agent, the pipeline starts without ✅. If not, the owner of that agent gets an accept/reject button. After that it is a normal pipeline.

**Why this priority**: It gives time-based and event-based work without a server.

**Independent Test**: Post one trigger message from a test bot. Check that the pipeline starts (allowlist) or that a button appears (no allowlist).

**Acceptance Scenarios**:

1. **Given** a GitLab schedule is set, **When** the schedule runs, **Then** a mention with task data appears in `#pipe-work`.
2. **Given** the trigger bot is in the allowlist of the mentioned agent, **When** the mention arrives and the plan is valid, **Then** the pipeline starts without ✅ and without a button.
3. **Given** the trigger bot is not in the allowlist, **When** the mention arrives and the plan is valid, **Then** the owner of the mentioned agent gets an accept/reject button and no step starts.
4. **Given** the button is shown, **When** the owner accepts, **Then** the pipeline starts. **When** the owner rejects, **Then** the plan is `failed` with `reason: rejected`, with no "Retry" button.
5. **Given** the button is shown, **When** a person other than the owner clicks, **Then** nothing changes.
6. **Given** the plan in the mention is not valid, **When** the mentioned agent checks it, **Then** it posts the errors, shows no button, and starts nothing.
7. **Given** a pipeline from a trigger bot runs, **When** it runs, **Then** the same plan check, trust, hop, claim, delegation gate, and timeout rules apply as for a chat pipeline.
8. **Given** a plan names the trigger bot as a step agent, **When** the plan check runs, **Then** the plan is invalid.
9. **Given** a trigger text has `flow:<name>` and a goal and the metadata has no `pipeline`, **When** the mention arrives, **Then** the mentioned agent expands the template with the `plan_flow` action of spec 003 (no LLM call), checks the plan, and applies the same gate.
10. **Given** a trigger has both a `pipeline` and a `flow:` word, or has neither, **When** the mention arrives, **Then** the system ignores it (`bad_payload`).

### Edge Cases

- The review capability fails or never ends. The step fails at the time limit with a "Retry" button (spec 003).
- The capability reports twice for one step. The second report is ignored.
- A "done" message for a step comes from an agent that does not hold the winning claim. It is ignored.
- The MR link is missing. When the capability has an `input_schema`, the step fails before the run with `reason: invalid_payload`. No external request is sent.
- Two agents have a capability with the tag `review`. The claim rule picks one. A review by the author's own agent is possible (DQ8 in plan.md).
- No agent lists a capability with the requested tag. The plan check rejects the plan before ✅ (spec 003).
- A bot with no agent card posts a trigger mention. The metadata is ignored.
- A bot with a card of `kind: agent` posts a top-level mention with a `pipeline`. It is ignored. Only `kind: trigger` can start a pipeline this way.
- A trigger bot posts a message with `next` (a handoff). It is ignored. A trigger bot is never a step agent.
- The trigger job posts to a wrong channel. No adapter acts on it.
- The trigger mention names two agents. The first named agent is the planner. The other agent ignores it.
- The mentioned agent is offline when the job runs. The adapter takes the mention at start (catch-up, spec 001).
- The reviewer adapter runs one call at a time (spec 001). While a review waits, other mentions for that adapter wait in the queue (DQ9 in plan.md).
- The CI job runs twice (a retry). Two threads start. The system does not remove this duplicate (DQ7 in plan.md).
- The trigger token leaks. The owner removes the trigger bot from the allowlist and rotates the token. After that, every trigger asks the owner.
- A trigger pipeline has a `write` step. The delegation gate of spec 004 applies.
- The trigger payload has `hop` that is not 0. The mention is ignored.
- The trigger has both a `pipeline` and a `flow:<name>` word, or a `flow:` word with no goal, or a goal text with no flow word and no `pipeline`. The mention is ignored (`bad_payload`).
- The trigger names an unknown flow. The planner posts a type 2 plan message with `could not build a plan (unknown flow)`. No button.
- A fixed `pipeline` from a trigger is a free plan unless the receiver verifies that it matches a template (`effective_source`). The `hop` limit follows the source.
- A review step in a plan from the planner or from a template carries `exclude_agents_of`. The author cannot review its own change (DQ8, closed by spec 003 FR-039).
- A wrapper prints `{status: failed}` with a non-zero exit code. The exit code wins: `RuntimeFailed`, no branch. An e2e wrapper that wants `on_fail` MUST exit 0.
- A wrapper lists a file that is a symbolic link, a directory, or larger than 10 MB. The upload is refused. The step fails with `upload refused`.

## Requirements *(mandatory)*

### Functional Requirements

**Review step**

- **FR-001**: A review step MUST be a normal plan step. Its capability MUST have the tag `review`. The system MUST NOT add a step type, a field `kind`, or review code to the core.
- **FR-002**: The owner MUST be able to give the tag `review` to a capability through the config map `tags` (spec 002). The system MUST NOT build a second review engine. wiz-review is the first implementation.
- **FR-003**: A step MUST be able to name `capability: "tag:review"` and `agent: "any"`. The system MUST also accept a fixed agent and a fixed capability ID for a review step.
- **FR-004**: The system MUST NOT start the next step before the agent of the review step posts `status: done`.
- **FR-005**: The review step MUST receive the change link. The link MUST come from the step `payload` or from the effective payload of spec 003 (`artifacts` and `context` of ALL earlier done steps, DQ2 in plan.md). An `input_schema` with `additionalProperties: false` MUST list `context` and `artifacts`, because `check_input` validates the effective payload.
- **FR-006**: The system MUST ignore a second `status: done` for the same step. It MUST NOT start the next step twice.

**Slow capabilities**

- **FR-007**: The system MUST keep a step `running` until the claiming adapter learns that the capability ended. The core MUST NOT know that a capability is slow.
- **FR-008**: A completion MUST reach the thread only as a message of the claiming agent that passes the trust checks of spec 003. The system MUST NOT accept a completion from any other source. The system MUST NOT add a new trust path.
- **FR-009**: When the capability ends with an error, the claiming adapter MUST post `status: failed` with a scrubbed reason and a "Retry" button. A runtime result with `status: failed` gives `reason: run_failed` and, when the plan step has `on_fail`, the branch handoff (type 11, no button). A non-zero exit code or a timeout gives `RuntimeFailed`: a "Retry" button and no branch (spec 003 FR-040).
- **FR-010**: The system MUST fail a step that does not end within the step time limit. The failure MUST have a reason and a "Retry" button (spec 003).
- **FR-011**: When the capability has an `input_schema`, the system MUST check the step payload before the run. A payload that fails the check MUST give `status: failed` and `reason: invalid_payload`. No capability code and no external request runs.
- **FR-012**: The wiz-review implementation MUST be a capability declared in the owner config. It MUST send one review request for one MR and wait for the drafts (DQ1 in plan.md). It MUST NOT send a second request for the same MR on a "Retry". It MUST NOT change the review behavior of wiz-review.

**Triggers**

- **FR-013**: Any bot with a card of `kind: trigger` MUST be able to start a pipeline. It posts a top-level mention in `#pipe-work`. The mention carries EITHER `pipe.task.v1` metadata that holds a fixed `pipeline`, OR the word `flow:<name>` with a non-empty goal in the text and no `pipeline` (DQ3 in plan.md). A mention with both, or with neither, MUST be ignored (`bad_payload`). A free goal text MUST NOT start a pipeline.
- **FR-014**: The mentioned agent MUST check the plan with the plan check of spec 003 (`validate_plan(plan, cards, starter, flows)`) before it applies the gate. For a `flow:` trigger, it MUST first expand the template with the `plan_flow` action of spec 003 (no LLM call). An invalid plan MUST give the error text and no button.
- **FR-015**: The mentioned agent MUST start the pipeline without ✅ and without a button when the trigger bot is in its allowlist (`in_allowlist`, spec 004). In every other case, the owner of the mentioned agent MUST get an accept/reject button, and no step starts before the click.
- **FR-016**: Only the owner of the mentioned agent MUST be able to accept or reject. A click from any other person MUST change nothing. A reject MUST give `status: failed` and `reason: rejected`, with no "Retry" button.
- **FR-017**: A trigger bot MUST have its own agent card with `kind: trigger` and no skills. It MUST only post trigger mentions. It MUST NOT be a step agent. The plan check MUST reject a plan that names it as a step agent. The system MUST ignore a handoff from it.
- **FR-018**: The system MUST ignore a trigger mention in six cases: the sender has no card, the card kind is not `trigger`, `hop` is not 0, the message is not top-level, it has both a `pipeline` and a `flow:` word, or it has neither.
- **FR-019**: A pipeline from a trigger bot MUST follow the same plan check, trust, hop, claim, delegation gate, and timeout rules as a chat pipeline.
- **FR-020**: The system MUST provide a CI job template that posts a trigger mention. GitLab CI MUST be the first example. The bot name for it is `pipe-gitlab`. The token MUST come from a masked CI variable. The template shape MUST also fit other CI tools.
- **FR-021**: The system MUST NOT add saved pipelines or recurring schedules from chat. GitLab schedules are edited in the GitLab UI.
- **FR-022**: The core MUST NOT name wiz-review, GitLab, or a review tool. The import-boundary test of spec 003 MUST cover the new core module.
- **FR-023**: No file, log line, or posted text of this feature MAY hold a token. The CI template MUST NOT print the token.
- **FR-024**: A declared long-task wrapper MUST follow one output contract for review, e2e, long tests, and any other long task (`contracts/slow-capability.md`): one JSON object on stdout with `text`, optional `status` (`done` or `failed`), `artifacts`, `data`, and `files`.
- **FR-025**: A wrapper that wants the `on_fail` branch MUST print `{"status": "failed"}` and exit with code 0. A non-zero exit code MUST give `RuntimeFailed` and MUST NOT branch.
- **FR-026**: The adapter MUST upload each path in `files` with `Transport.upload_file` and MUST put the returned links in `artifacts`. A path MUST be a regular file inside `~/.pipe/run/`, not a symbolic link, and at most 10 MB. Else the step MUST fail with `reason: upload refused`. The core never reads the file. The Slack scope is `files:write`.
- **FR-027**: The planner prompt and the templates MUST set `exclude_agents_of` on a review step. Spec 005 adds no claim rule (DQ8 is closed by spec 003 FR-039).

### Key Entities

- **Review step**: A normal step. Its capability has the tag `review`. It has a goal, a payload with the change link, and a state.
- **Review capability**: A capability with the tag `review`. wiz-review is the first implementation.
- **Completion**: The `status: done` (or `failed`) message of the claiming agent. It is the only end signal of a step.
- **Slow capability**: A capability whose implementation ends after the claim. The claiming adapter waits for it.
- **Trigger bot**: A Slack bot with a card of `kind: trigger` and no skills. It only posts trigger mentions. `pipe-gitlab` is the example name.
- **Trigger mention**: The top-level message that starts a pipeline. It has a mention of the agent and `pipe.task.v1` metadata with a `pipeline`.
- **Trigger gate**: The decision `allow` (trigger bot in the allowlist) or `ask` (button for the owner).
- **Trigger template**: A small script and a CI job file that post a trigger mention.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tests, a review step starts a reviewer agent, and the next step starts only after that agent posts `status: done`.
- **SC-002**: In 100% of tests, a second `status: done` for the same step causes no second step start.
- **SC-003**: In 100% of tests, a slow capability keeps its step `running` until the end. A "done" from another source changes nothing.
- **SC-004**: In 100% of builds, the import-boundary test passes: no core module names wiz-review, GitLab, or a review term.
- **SC-005**: A GitLab schedule run gives a mention in `#pipe-work` and a started pipeline in under 2 minutes (allowlisted trigger bot).
- **SC-006**: In 100% of tests, a trigger from a bot in the allowlist starts without ✅ and without a button. In every other case the owner gets a button and no step starts before the click.
- **SC-007**: In 100% of tests, a trigger from a bot with no card, or with a card of `kind: agent`, starts nothing.
- **SC-008**: In 100% of tests, a plan that names a trigger bot as a step agent is rejected.
- **SC-009**: A review step that hangs shows `failed` and a "Retry" button within one minute after the time limit.
- **SC-010**: In 100% of tests, a click from a person who is not the owner changes nothing.
- **SC-011**: In 100% of tests, a pipeline from a trigger bot follows the same rules as a chat pipeline (hop, claim, timeout, delegation gate).
- **SC-012**: In 100% of tests, no new file of this feature holds a token, and the template output does not print the token.
- **SC-013**: In 100% of tests, a trigger with both a `pipeline` and a `flow:` word, or with neither, starts nothing (`bad_payload`).
- **SC-014**: In 100% of tests, a `flow:` trigger gives a plan with no runtime call (the fake runtime has zero planner calls).
- **SC-015**: In 100% of tests, a wrapper result `status: failed` with exit code 0 takes `on_fail`, and a non-zero exit code does not.
- **SC-016**: In 100% of tests, a file in `files` that is outside `~/.pipe/run/`, a symbolic link, or over 10 MB gives `upload refused` and no upload call.

## Assumptions

- Specs 001 to 004 exist, with the second batch of spec 003 (constitution 1.3.0): late binding by tag, capabilities declared in the config, the `Transport` port, `input_schema` and `output_schema`, `effective_payload`, `exclude_agents_of`, `on_fail`, `plan_flow`, and `upload_file`. Plan.md lists the few changes that 005 still makes.
- wiz-review stays the review engine and keeps its present behavior. The recommended option needs no change in the wiz-review repo (DQ1 in plan.md).
- The owner of the reviewer agent exposes the review capability. A capability that uses the owner credentials is `owner-only` until the owner exposes it (principle III).
- GitLab Pipeline schedules are created in the GitLab UI.
- The Slack workspace and `#pipe-work` exist.
- The owner of the wiz-review agent wrapper is the repository owner in the MVP (decided 2026-11-26).

## Notes for /speckit-plan

- No core code for review. Reuse the plan check, claim, timeout, and Retry of spec 003.
- One new core module for triggers. Reuse `in_allowlist` of spec 004.
- The slow-capability rule needs no new message type.
- Templates (stdlib only): a trigger post script, a CI job file, and a review capability wrapper.
- Write the unit tests first (constitution principle VII).
