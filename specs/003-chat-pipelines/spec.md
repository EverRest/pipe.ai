# Feature Specification: Pipelines from Chat

**Feature Branch**: `003-chat-pipelines`

**Created**: 2026-11-25

**Status**: Draft

**Input**: User description: "A human describes a chain of work in one message and names agents. The first named agent builds a plan from the agent cards, shows it in the thread, and waits for ✅. After ✅, the agents do the steps one by one in the same thread. Each step shows its status. The last step can ask a human to approve."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plan a pipeline and approve it (Priority: P1)

A person writes one message that names two or more agents and a chain of work. The first named agent is the planner. It reads the agent cards, builds the plan, and checks it. It posts the plan in the thread with the status `needs_approval`. The person approves with ✅.

**Why this priority**: The plan check is the safety gate. No work may start without it.

**Independent Test**: Post a chain request with two agents. Check that a plan appears and that no work starts before ✅.

**Acceptance Scenarios**:

1. **Given** a message names two agents and a chain of work, **When** the first agent reads it, **Then** the agent posts a plan with the status `needs_approval`.
2. **Given** a plan names an unknown agent, **When** the planner checks the plan, **Then** the plan is rejected before ✅ and the thread shows the errors.
3. **Given** a plan needs a capability that the card of the agent does not list (a hidden capability), **When** the planner checks the plan, **Then** the plan is rejected before ✅.
   - **Given** a plan has a step with access `write`, **Then** the plan is rejected before ✅ (not supported before spec 004).
4. **Given** a valid plan is posted, **When** the thread starter adds ✅, **Then** the pipeline starts.
5. **Given** a valid plan is posted, **When** a person who is not the thread starter adds ✅, **Then** the pipeline does not start.

---

### User Story 2 - Run the steps one by one (Priority: P1)

After ✅, each agent does its step in the same thread. Each step ends with a status and names the next agent. Each step shows its status in the thread. The last step can ask a human to approve with a button. Then the thread gets the status `done`.

**Why this priority**: This is the core value: agents of different owners work in a chain.

**Independent Test**: Approve a plan with two steps. Check that step 2 starts only after step 1 is `done`, and that the thread ends as `done`.

**Acceptance Scenarios**:

1. **Given** an approved plan, **When** step 1 ends with `done`, **Then** the agent of step 2 starts.
2. **Given** the last step is a human approval, **When** the thread starter or the agent owner clicks the button, **Then** the thread gets the status `done`.
3. **Given** each step runs, **When** its state changes, **Then** the thread shows the new status (`claimed`, `running`, `waiting`, `done`, or `failed`).

---

### User Story 3 - Reject untrusted and looping input (Priority: P1)

The agents act only on trusted data. They stop loops.

**Why this priority**: Thread content is untrusted input. A mistake here lets any person or bot control an agent.

**Independent Test**: Post metadata from a bot without a card. Check that nothing happens. Post a task with `hop` 4. Check that it is refused.

**Acceptance Scenarios**:

1. **Given** a message has task metadata from a bot that has no agent card, **When** an adapter reads it, **Then** the adapter ignores the metadata.
2. **Given** a task of a free plan has `hop` 4, **When** an adapter reads it, **Then** the adapter refuses it.
3. **Given** two agents hand a step back and forth in a free plan, **When** the hop count passes 3, **Then** the thread stops. (A verified template has the limit 5: see User Story 12.)

---

### User Story 4 - Resolve duplicate claims (Priority: P2)

Two agents may take the same step. Each posts a claim. The claim with the lowest `ts` wins. The other agent stops.

**Why this priority**: Without this rule, one step could run twice.

**Independent Test**: Post two claims for one step. Check that only the earlier one runs.

**Acceptance Scenarios**:

1. **Given** two agents claim one step, **When** the adapters compare the claims, **Then** the claim with the lowest `ts` wins.
2. **Given** an agent lost the claim, **When** it sees the winner, **Then** it stops work on that step.

---

### User Story 5 - Handle a hung step (Priority: P2)

A step has a time limit. When the limit passes, the step fails with a reason and a "Retry" button. The system does not retry by itself.

**Why this priority**: A silent hang blocks the whole thread.

**Independent Test**: Run a step that never ends. Check that it becomes `failed` at the limit with a "Retry" button.

**Acceptance Scenarios**:

1. **Given** a step runs longer than the step time limit, **When** the limit passes, **Then** the step gets `failed` with a reason and a "Retry" button.
2. **Given** a step is `failed`, **When** the thread starter or the agent owner clicks "Retry", **Then** the step runs again.
3. **Given** a step is `failed`, **When** no person clicks "Retry", **Then** the step does not run again.
4. **Given** the owner of the next agent is offline, **When** the step is due, **Then** the step gets `waiting` with the reason `owner offline`, and the wait time is recorded.

---

### User Story 6 - Measure the experiment (Priority: P3)

A team member runs one script. The script reads the task data in `#pipe-work` and prints the experiment metrics from design brief §10.

**Why this priority**: The MVP is an experiment. Without the metrics, the team cannot decide to continue or to stop.

**Independent Test**: Run the script on a test channel with known threads. Check that each metric has the expected value.

**Acceptance Scenarios**:

1. **Given** threads with delegation steps and MR links, **When** the script runs, **Then** it prints the number of delegations between owners with a merged MR, per week.
2. **Given** finished and stopped pipelines, **When** the script runs, **Then** it prints the share of pipelines that finished without manual help between steps.
3. **Given** agent messages with 🔇 reactions, **When** the script runs, **Then** it prints the share of noisy agent messages and the number of threads stopped by the `hop` limit.
4. **Given** steps with `status: waiting` and `reason: owner offline`, **When** the script runs, **Then** it prints the median wait time.

---

### User Story 7 - Late binding by tag (Priority: P2)

A plan step can name a capability tag instead of one agent. The step has `agent: "any"` and `capability: "tag:<tag>"`. Any agent can claim it when its card has an exposed capability with that tag, the access level fits, and the gate rules of spec 004 pass. The claim with the lowest `ts` wins.

**Why this priority**: The planner does not need to know who is online or who owns the right tool. Any fitting agent can do the work.

**Independent Test**: Post a plan with a tag step. Start two adapters whose cards have the tag. Check that exactly one runs the step.

**Acceptance Scenarios**:

1. **Given** a plan has a step `agent: any`, `capability: tag:review`, **When** no trusted card has an exposed capability with the tag `review`, **Then** the plan is rejected before ✅.
2. **Given** a valid tag step reaches its turn, **When** two eligible agents claim it, **Then** the claim with the lowest `ts` wins and the other agent stops.
3. **Given** an agent has no exposed capability with the tag, **When** the handoff for a tag step arrives, **Then** that agent does nothing.
4. **Given** nobody claims a tag step within the step time limit, **When** the limit passes, **Then** the step gets `failed` with `reason: no_claimer` and a "Retry" button.
5. **Given** a tag step has `access: write`, **When** an agent wins the claim, **Then** the gate of spec 004 applies to that agent (its allowlist and its owner).

---

### User Story 8 - Run a declared capability with optional schemas (Priority: P2)

A step can name a capability that the owner declared in config (`exec` or `http`, spec 002). The core picks the runtime adapter by the runtime of the capability. A capability can have an input schema and an output schema. The core checks the step `payload` before the run and the result after it.

**Why this priority**: This makes the system work with any tool, not only with Claude skills.

**Independent Test**: Run a step for an `exec` capability with an input schema. Send a good payload and a bad payload. Check that the bad one fails before the run.

**Acceptance Scenarios**:

1. **Given** a step names a declared `exec` capability, **When** the step runs, **Then** the `exec` adapter runs the command and the step gets its `text`, `status`, and `artifacts`.
2. **Given** the capability has an `input_schema`, **When** the step `payload` does not match, **Then** the step fails with `reason: invalid_payload` and no runtime runs.
3. **Given** the capability has an `output_schema`, **When** the result `data` does not match, **Then** the step fails with `reason: invalid_result`.
4. **Given** the capability has no schema, **When** the step runs, **Then** the behavior is the same as before.
5. **Given** a person who is not the owner starts a step for a declared capability, **When** the capability is not exposed now, **Then** the step fails with `reason: capability not available` and nothing runs.

### User Story 9 - Ask a question in the middle of a step (dialog step) (Priority: P2)

A step can need a human answer. Its agent ends the run with `status: waiting` and `reason: needs_input`. The `text` is the question. Only the thread starter or the owner of that agent can answer. The answer resumes the SAME step on the SAME agent, with the thread as context. `hop` does not grow. While the step waits, the step timer is paused. When nobody answers within `dialog_timeout_h`, the step fails with `reason: dialog_timeout` and a "Retry" button.

**Why this priority**: Brainstorm and planning work needs a dialog. Without it, an agent must guess.

**Independent Test**: Use `FakeRuntime` that returns `waiting` once and `done` the second time. Post the answer. Check that the same step and the same agent run twice, with one claim and no `hop` change.

**Acceptance Scenarios**:

1. **Given** a step returns `waiting` with `needs_input`, **When** the stepper reads the result, **Then** the thread shows the question as a type 10 message (`waiting`) that mentions the thread starter, and no `next` handoff goes out.
2. **Given** the thread starter replies in the thread and mentions the agent, **When** the agent reads the reply, **Then** the same step runs again on the same agent, with no new claim and the same `hop`.
3. **Given** the owner of the agent replies, **Then** the same result as in scenario 2.
4. **Given** another person replies, **When** the agent reads it, **Then** the step stays `waiting`. The reply is a normal chat message (spec 001).
5. **Given** nobody answers within `dialog_timeout_h`, **When** the limit passes (also after a restart of the adapter), **Then** the step is `failed` with `reason: dialog_timeout` and a "Retry" button. No retry starts alone.
6. **Given** the step waits for 3 hours and `step_timeout_min` is 30, **When** the answer comes, **Then** the step does not fail with `timeout`. The step timer counts only the time of a run.

---

### User Story 10 - Share context, gate a step, and propose a plan (Priority: P2)

Each step gets the `text` summary and the `artifacts` of all previous steps in its payload. A step can have a gate: after it ends, the thread waits for a new ✅ before the next step starts. A step can also return a proposed plan. The proposal needs a new ✅. A step never starts work by itself.

**Why this priority**: Flows such as `feature-dev` need the result of earlier steps, and they need a human check after a task proposal.

**Independent Test**: Run a three-step plan with fake runtimes. Check the payload of step 3. Add a gate on step 1. Check that step 2 starts only after ✅.

**Acceptance Scenarios**:

1. **Given** steps 0 and 1 are `done`, **When** step 2 starts, **Then** its effective payload holds `context` with the `text` and `artifacts` of both steps, in step order, and `artifacts` with all links.
2. **Given** a step `text` is longer than 1000 characters, **When** the next step starts, **Then** the context holds the first 1000 characters and all links. Large context goes by link.
3. **Given** step 0 has `gate: approval` and ends `done`, **When** the core reads the thread, **Then** the thread shows the type 5 message `needs_approval` and step 1 does not start.
4. **Given** ✅ comes from the thread starter or the planner owner on that message, **When** the author adapter reads it, **Then** it posts the `done` result with `next` once.
5. **Given** ✅ comes from another person, or ✅ is on the plan message only, **When** the core reads it, **Then** nothing starts.
6. **Given** a step returns a proposal that passes `validate_plan`, **When** the stepper reads the result, **Then** the type 5 message is `needs_approval`, holds the proposal, and no step starts. After a new ✅ the proposal becomes context only. The pipeline goes on with its own steps.
7. **Given** a proposal fails `validate_plan`, **When** the stepper reads it, **Then** the step is `failed` with `reason: invalid_proposal` and the errors, and a "Retry" button.

---

### User Story 11 - Exclude agents and branch on failure (Priority: P2)

A step can exclude the agents that did earlier steps (`exclude_agents_of`). A step can name one failure branch (`on_fail`). The planner sets `exclude_agents_of` for a step that reviews earlier work.

**Why this priority**: A review by the author is not a review. A failed test run needs a diagnosis step.

**Independent Test**: Run a plan with a tag step that excludes step 0. Let agent A win step 0. Let A claim step 1. Check that the claim is ignored. Run a plan with `on_fail`. End step 0 with `run_failed`, and with `timeout`. Check that only the first gives a branch.

**Acceptance Scenarios**:

1. **Given** step 2 has `exclude_agents_of: [1]` and agent A holds step 1, **When** A claims step 2, **Then** the claim is ignored (`excluded`). Another eligible agent can claim it.
2. **Given** the only agent that offers the tag of step 2 is the fixed agent of step 1, **When** `validate_plan` runs, **Then** the plan is rejected before ✅.
3. **Given** step 0 has `on_fail: 1` and ends `failed` with `reason: run_failed`, **When** the claimant reads the result, **Then** it posts one type 11 message (`failed`, `next` for step 1). The flow ends after step 1.
4. **Given** step 0 ends `failed` with `timeout`, `no_claimer`, `invalid_payload`, or `dialog_timeout`, **When** the claimant reads it, **Then** the thread shows `failed` with a "Retry" button and no branch.
5. **Given** step 0 ends `done`, **When** the core reads the thread, **Then** the branch step is skipped and the thread is `done`.
6. **Given** a plan has two steps with `on_fail`, or a target that is not the last step, **When** `validate_plan` runs, **Then** the plan is rejected.
7. **Given** a free plan uses `gate`, `on_fail`, and `exclude_agents_of`, **When** `validate_plan` runs, **Then** the same structure rules apply and the `hop` limit stays 3.

---

### User Story 12 - Plan source and `hop` limit by source (Priority: P1)

A plan has a `source`: `template:<name>@<hash>` or `free`. The source is only a claim. Every adapter works out the effective source itself from its own template files (spec 006). The `hop` limit is 5 for a verified template and 3 for every other plan. A message with a `flow:<name>` word is a pipeline request, also with one named agent. The planner can answer with a template name. The core expands the template.

**Why this priority**: This is a security point (constitution 1.3.0). A plan must not raise its own limit.

**Independent Test**: Run `effective_source` and `hop_limit` with a fake template and with changed plans. Run `route` with a handoff of `hop` 4.

**Acceptance Scenarios**:

1. **Given** a plan declares `template:<name>@<hash>`, **And** the adapter has that template with the same hash, **And** the steps match its shape, **When** a handoff has `hop` 4, **Then** the adapter accepts it.
2. **Given** the same plan and `hop` 6, **Then** the adapter refuses it.
3. **Given** the hash differs, the name is unknown, the steps differ, or `flows` is empty, **When** a handoff has `hop` 4, **Then** the adapter refuses it with the text `hop limit exceeded (plan source not verified)`.
4. **Given** a plan declares `free` and has 4 bot steps, **When** `validate_plan` runs, **Then** the plan is rejected.
5. **Given** a message has one agent mention and a `flow:bugfix` word, **When** the first agent reads it, **Then** the decision is `plan_flow` and no runtime runs.
6. **Given** the planner LLM returns `flow: <name>` and also `steps`, **When** the planner reads the output, **Then** it ignores `steps` and the core expands the template.
7. **Given** a person writes "save this plan as a flow", **When** the planner reads it, **Then** no file is written.

### Edge Cases

- A tag step names a tag that matches several capabilities of one agent. The agent binds the lowest capability ID (`bind_step`).
- A tag step comes before a human step. Only the thread starter can be the human of that step, because the agent is not known at plan time.
- The first claimer of a `write` tag step is rejected by its owner. The step ends as `failed`, `rejected` (spec 004). Other eligible agents do not get a second chance in this version (FR-046).
- A step asks a question and nobody answers within `dialog_timeout_h`. The step ends `failed`, `dialog_timeout`, with a "Retry" button (FR-036).
- A person who is neither the thread starter nor the agent owner answers a question. The step stays `waiting` (FR-036).
- A step returns a proposal that fails `validate_plan`. The step ends `failed`, `invalid_proposal` (FR-038).
- A step with `on_fail` ends `failed` with `timeout`. The flow does not branch. It shows "Retry" (FR-040).
- Two adapters of one bot get the same gate release. One `done` message is posted (FR-043).
- A plan declares a template source that this adapter cannot verify. The effective source is `free` (FR-042).
- An `exclude_agents_of` rule leaves no agent that can claim the step. `validate_plan` rejects the plan when it can prove this. Else the step ends `failed`, `no_claimer` at run time (FR-039).
- A `payload` is given for a capability that has no `input_schema`. The core passes it as it is.
- A person edits the plan message after the plan is posted.
- A person adds ✅ before the plan check finishes.
- A named agent has an agent card but its owner is offline.
- The same Slack event arrives twice.
- A plan has a step for a human (`human:<user_id>`). The step has no capability.
- An agent restarts in the middle of a pipeline and finds an open step for itself.
- Two claims have the same `ts`.
- The thread starter is also the agent owner.
- A plan step names a capability that no longer exists in the card at run time.
- A card has no `bot_user_id` or a wrong one (the message `user` differs).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST act only on a direct mention of an agent, or on a task whose next agent is that agent.
- **FR-002**: The first agent that the message names MUST be the planner. A message is a pipeline request when it names two or more distinct agents that have a card, or when it has a `flow:<name>` word and names at least one agent that has a card (FR-044). A message with one agent and no `flow:` word is a normal chat.
- **FR-003**: The planner MUST build the plan from the agent cards.
- **FR-004**: The planner MUST check that every agent in the plan has a card (a tag step follows FR-028), that the card lists the capability of the step (the card lists exposed capabilities only), and that the access level is supported. It MUST reject a plan with more agent steps than the `hop` limit of its effective source: 3 for a free plan, 5 for a verified template (FR-042). It MUST apply the structure rules of the fields `exclude_agents_of`, `gate`, and `on_fail` (FR-039, FR-040, FR-043). It MUST reject a human step whose user is neither the thread starter nor the owner of the agent that posts the button. It MUST reject a plan that fails a check, before ✅.
- **FR-005**: The planner MUST post the plan in the thread with the status `needs_approval`.
- **FR-006**: The system MUST start the pipeline only after ✅ from the thread starter or the owner of the planner agent.
- **FR-007**: The system MUST ignore ✅ and button clicks from any other person.
- **FR-008**: The system MUST trust task metadata only from bots that have an agent card. It MUST ignore other metadata.
- **FR-009**: The system MUST refuse a task with `hop` greater than the `hop` limit of the effective source of its plan (FR-042): 3 for a free plan, 5 for a verified template. Every handoff to an agent adds 1 to `hop`. A dialog resume, a "Retry", a gate release, and a plan proposal add nothing.
- **FR-010**: The system MUST allow a step to pass back and forth between two agents at most two times in a free plan. This follows from the `hop` limit 3. A verified template has the limit 5, and the `hop` limit is then the only guard.
- **FR-011**: The system MUST run steps one by one. A step starts only after the previous step has the status `done`.
- **FR-012**: Each step MUST show its status in the thread: `needs_approval`, `claimed`, `running`, `waiting`, `done`, or `failed`. A step can be `needs_approval` after its run, when it has a gate or a plan proposal (FR-038, FR-043). A step is `waiting` for a person when it asks a question (FR-036).
- **FR-013**: The system MUST support a last step for human approval, with a button. After approval, the thread MUST get the status `done`.
- **FR-014**: When two agents claim one step, the claim with the lowest `ts` MUST win. The other agent MUST stop.
- **FR-015**: The system MUST fail a step that runs longer than the step time limit. The default limit is 30 minutes. The failure MUST show a reason and a "Retry" button.
- **FR-016**: The system MUST NOT retry a failed step by itself.
- **FR-017**: The system MUST set the status `waiting` with the reason `owner offline` when the owner of the next agent is offline. It MUST record the wait time.
- **FR-018**: The system MUST drop a repeated Slack event, by the event ID. A button click has no event ID from Slack. For a click, the system MUST act only when the step is in the state that the button needs (for example, `Retry` only for a `failed` step, and an approval only while the gate waits). A second click then has no effect. The system MAY also keep a short in-memory set of click trigger IDs as an extra guard. That set is not stored, so the state check is the real guard.
- **FR-019**: At start, the system MUST find open steps whose next agent is itself and continue them.
- **FR-020**: Task data MUST follow `pipe.task.v1`: `v`, `task_id`, `phase`, `status`, `by`, `hop`, and the optional `access`, `pipeline`, `step`, `next`, `artifacts`, and `reason`. A plan step is `{agent, capability, access, goal}` (`agent` may be `any` and `capability` may be `tag:<tag>`, FR-028; the optional `payload`, FR-032; the optional `exclude_agents_of`, `gate`, and `on_fail`, FR-039, FR-040, FR-043). The `pipeline` has the optional `source` (FR-042). The task data has no field named `kind` and no field named `skill`.
- **FR-021**: The system MUST NOT save pipelines or make recurring pipelines from chat. No chat message, no button, and no agent run MAY write a template file. Templates from git (`flows/`) and owner overrides (`~/.pipe/flows/`) are allowed (spec 006). The owner edits the files by hand.
- **FR-022**: For a step that a person other than the agent owner started, the system MUST run the runtime with the capability of the step and the access level of the step, and with `requester_is_owner` false. The runtime adapter MUST load exposed capabilities only and MUST give no file tool. No `owner-only` item loads in any step.
- **FR-023**: The system MUST provide a metrics script. The script MUST read only the task data in `#pipe-work` (including the `artifacts` links) and the MR state from a replaceable provider. GitLab is the first provider. The script MUST NOT need a database.
- **FR-024**: The pipeline core (routing, plan, steps, trust, claim, hop, timeout, catch-up) MUST work only with `capability_id` values from agent cards. It MUST NOT name plugins, skills, MCP, runtime tool names, wiz-review, or GitLab. It MUST handle tags as opaque strings and hold no standard tag name. A runtime adapter turns capability IDs into runtime flags. The import-boundary test MUST cover every module in `src/pipe/core/`, also the modules that specs 005 and 006 add.
- **FR-025**: A plan step MUST have the form `{agent, capability, access, goal}`, with the optional `payload` (FR-032) and (spec 004) `target`. `access` is `read`, `write`, or `approve`. A bot step MAY also have `exclude_agents_of`, `gate`, and `on_fail` (FR-039, FR-040, FR-043). This feature MUST support `read` steps, `approve` steps, and the human step. The system MUST refuse `write` steps in this feature alone (spec 004 adds them, with the owner gate; after 004, a `write` step is valid, a step can have `needs_approval` as a gate state, and a rejected step has no "Retry"). A `human:<user_id>` step has `access: approve` and no capability. `approve` runs no runtime.
- **FR-026**: The system MUST mention the next agent with `Transport.mention(bot_user_id)` (Slack: `<@bot_user_id>`), with `bot_user_id` from the card of that agent (spec 002). The system MUST NOT need the `users:read` scope and MUST NOT call `bots.info` or `users.info`.
- **FR-027**: The core MUST give the runtime adapter only the capability IDs to load, the access level, and whether the requester is the agent owner. The runtime adapter MUST map them to its own flags and config.

- **FR-028**: A plan step MAY have `agent: "any"` and `capability: "tag:<tag>"`. The two values come together. A tag is lower case `[a-z0-9-]` with at most 32 characters. A tag step MUST have `access` `read` or `write`. `validate_plan` MUST check that at least one trusted card has an exposed capability with that tag whose access fits. Else it MUST reject the plan before ✅.
- **FR-029**: The access of a step fits the access of a card capability ONLY when both are equal, or when the card capability has no `access` (decision LB1, confirmed by the owner on 2026-11-26). There is no other fit rule: `write` does not cover `read`, and `read` does not cover `write`. The core MUST use this rule for tag steps and for fixed-agent steps.
- **FR-030**: A tag step handoff MUST mention every agent with a fitting card capability. Each of those agents MAY claim the step. The claim rule is unchanged: the lowest `ts` wins (FR-014). A claim from an agent that is not eligible MUST be ignored. After the claim, only the winner MAY post later messages for that step. The `hop` rule and the claim contest are unchanged.
- **FR-031**: When no agent claims a tag step within the step time limit, the sender of the handoff MUST post `failed` with `reason: no_claimer` and a "Retry" button. "Retry" posts the handoff again with the same `hop`. The system MUST NOT do it by itself.
- **FR-032**: A plan step MAY have a `payload` (a JSON object, at most 2000 characters as canonical JSON). When the capability has an `input_schema`, the core MUST validate the `payload` before the run, after the claim and before any gate. A failure MUST end the step with `status: failed` and `reason: invalid_payload`. No runtime runs. A missing `payload` counts as `{}`.
- **FR-033**: When the capability has an `output_schema`, the core MUST give it to the runtime adapter in the run request. The adapter passes it to its runtime if the runtime supports it. The core MUST validate `RuntimeOutput.data` against it. A missing or bad `data` MUST end the step with `reason: invalid_result`. Without a schema, nothing changes.
- **FR-034**: The core MUST pick the runtime adapter by the `runtime` value of the capability of the step (a pure function). The default adapter (planner, chat) is `runtime.name`. The adapters `exec` and `http` MUST run a declared capability only when it is exposed now (also for a step that the owner started). The environment of an `exec` run MUST hold only the variables of `env_allow` and `PIPE_RUNTIME=1`. The adapter MUST apply `scrub` and `escape_mentions` to the output.
- **FR-035**: The trust and claim rules MUST use the neutral identities `sender_id`, `sender_is_bot`, `sender_handle`, and `card_owner_id` (spec 001 contracts/transport.md). They MUST NOT read a raw chat field.

- **FR-036**: A step MAY end with `status: waiting` and `reason: needs_input` (a dialog step). The `text` is the question. The system MUST post it as a type 10 message that mentions the thread starter. Only the thread starter and the card owner of the agent that asked MAY answer. An answer is a thread reply that mentions that agent. A valid answer MUST resume the SAME step on the SAME agent, with the thread as context. It MUST NOT make a new claim. It MUST NOT change `hop`. The step timer (`step_timeout_min`) MUST count only the time of a run, so it is paused while the step waits. The config key `dialog_timeout_h` (default 24) MUST set the longest wait. After it, the step MUST end `failed` with `reason: dialog_timeout` and a "Retry" button, also when the adapter restarted during the wait. A reply from any other person MUST NOT resume the step.
- **FR-037**: The `effective_payload` of a step MUST hold the `text` and the `artifacts` of ALL previous steps that are `done`. The key `context` is a list of `{step, text, artifacts}` in step order. The key `artifacts` is the list of all links, in order, with no duplicate. A key that the plan `payload` sets wins. The core MUST cut each `text` to 1000 characters and all texts together to 4000 characters. Large context MUST go by link: the capability sends a file with `Transport.upload_file` and puts the link in `artifacts`. Step 0 gets neither key. `check_input` validates the effective payload (decision N2).
- **FR-038**: A step MAY return a proposed plan (`RuntimeOutput.proposal`). The system MUST check it with `validate_plan` as a free plan. An invalid proposal MUST end the step `failed` with `reason: invalid_proposal` and the errors. A valid proposal MUST give a type 5 message with `status: needs_approval`, the `pipeline`, and no `next`. The next step MUST NOT start before a NEW ✅ on that message from the thread starter or the owner of the planner (FR-043). A step MUST NEVER start work by itself. A proposal MUST NOT start any step. An approved proposal is context only: the pipeline goes on with its own steps. A template stays a template (spec 006 DQ12 = a).
- **FR-039**: A bot step MAY have `exclude_agents_of`: a list of at most 5 indexes of earlier bot steps. A claim for the step from an agent that holds an excluded step MUST be ignored (`excluded`), in `route` and in `check_task_msg`. `validate_plan` MUST reject a plan in which a fixed step names an agent that holds an excluded fixed step, and a plan in which no eligible card can claim a tag step after the exclusion (`exclusion_deadlock`). Else the step ends `failed`, `no_claimer` at run time. The planner MUST set the field for a step that reviews or checks earlier work. There is no general rule for it (spec 005 DQ8 is closed by this field).
- **FR-040**: A bot step MAY have `on_fail`: the index of the branch step. A plan MUST have at most ONE `on_fail`. The target MUST be the last step. The last step MUST be a bot step with no `on_fail`. The step with `on_fail` MUST NOT be the last step. A plan with `on_fail` MUST have no human step. The plan MUST have no loop. The branch MUST be taken only when the step ends `failed` with `reason: run_failed`. A timeout, `no_claimer`, `invalid_payload`, `invalid_result`, `invalid_proposal`, `dialog_timeout`, `rejected`, `interrupted`, `capability not available`, and a hop refusal MUST NOT branch: they use "Retry". The branch is a type 11 message (`failed`, with `next`). A thread MUST have at most one. The flow MUST end after the branch step. On success the branch step MUST be skipped.
- **FR-041**: A free plan MAY use `gate`, `on_fail`, and `exclude_agents_of`. The same structure rules apply (FR-039, FR-040, FR-043). The `hop` limit stays 3 (spec 006 DQ11 = a).
- **FR-042**: A plan MUST carry `pipeline.source`: `template:<name>@<hash>` or `free`. A missing value means `free`. The planner core sets it. The LLM never writes it. `validate_plan(plan, cards, starter, flows)` and every receiver (`route`) MUST work out the effective source with the pure function `effective_source`. The result is `template` only when the adapter has a template of that name, the hash of its parsed file equals the declared hash, and the plan steps match the template shape (spec 006). In every other case it is `free`. The limit is `hop_limit(source)`: 3 for `free` (`MAX_HOP_FREE`) and 5 for `template` (`MAX_HOP_TEMPLATE`). When the declared source is a template and the effective source is `free`, the refusal text MUST say `hop limit exceeded (plan source not verified)`. Two adapters with different template files MUST fail closed with this text (spec 006 DQ10 = a). `ThreadState.flows` holds the valid templates of the adapter.
- **FR-043**: A bot step MAY have `gate: approval`. After the step ends `done`, the step result MUST be a type 5 message with `status: needs_approval` (a mid-flow approval, spec 006 DQ6 = a). A ✅ on that message from the thread starter or the owner of the planner MUST release it. On release, the adapter that posted the message MUST post what the step would have posted without the gate (the `done` result with `next`, the approval request of a human step, or the final result), once. A ✅ from another person MUST change nothing. A gate on the last step MUST end the thread only after ✅. A step result with a proposal MUST be gated, also without `gate`.
- **FR-044**: A message with a `flow:<name>` word (`flow_word`) that names at least one agent with a card MUST be a pipeline request. If this adapter is the first named agent, the decision MUST be `plan_flow`, and the planner MUST expand the template with no LLM run (spec 006). The planner prompt MAY list the templates (name and description). The planner output MAY have `flow: <name>`. Then the core MUST expand the template, and it MUST ignore any `steps` of the LLM.
- **FR-045**: The task messages MUST include these types, each with a trust check (contracts/task-metadata.md): type 10 (dialog question, `by` equals the step agent), type 11 (branch handoff, `by` equals the step agent, the plan step has `on_fail` equal to `next.payload.step`, `reason: run_failed`), and type 5 with `needs_approval` (`by` equals the step agent, a `pipeline` counts only when it passes `validate_plan`). `route` MUST have the actions `plan_flow`, `release`, `resume`, and `expire_dialog`.
- **FR-046**: When the first claimer of a `write` tag step is rejected by its owner, the step MUST end `failed` with `reason: rejected`. No other eligible agent MAY get a second claim, and there is no "Retry" (spec 004). This is a known limit of this version (decided, deferred).

### Key Entities

- **Pipeline**: An ordered list of steps in one thread. It has a starter and an approval state.
- **Step**: One unit of work. It has an agent (a bot, `any`, or a human), a capability (a capability ID, a `tag:<tag>`, or none for a human), an access level, a goal, an optional payload, and a status.
- **Task state (`pipe.task.v1`)**: The data in a thread message that carries the phase, the access level, the status, the hop count, the plan, and the next step.
- **Claim**: A message that says one agent takes a step. It has a time (`ts`).
- **Agent card**: Comes from spec 002. It is the source of trust, the list of capabilities (`skills[].id` is the `capability_id`), and the `bot_user_id` for mentions.
- **Plan source**: `template:<name>@<hash>` or `free`. It is a claim. Every adapter works out the effective source.
- **Dialog question**: A type 10 message. It holds the question of a step that waits for a human answer.
- **Gate / proposal**: A type 5 message with `needs_approval`. It waits for a new ✅. A proposal is a plan that a step suggests. It is context only after approval.
- **Branch handoff**: A type 11 message. It sends a failed step (`run_failed`) to the branch step.
- **Run request**: What the core gives to the runtime adapter for one run: the capability IDs to load, the access level, `requester_is_owner`, and the optional `output_schema`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tests, a plan with an unknown agent or a hidden capability is rejected before ✅.
- **SC-002**: In 100% of tests, ✅ from a person who is not allowed does not start the pipeline.
- **SC-003**: In 100% of tests, metadata from a bot without a card causes no action.
- **SC-004**: In 100% of tests, a task of a free plan with `hop` 4 is refused and no work runs. (The limit for a verified template is SC-023.)
- **SC-005**: In 100% of tests with two claims, exactly one agent runs the step, and it is the one with the lowest `ts`.
- **SC-006**: A hung step shows `failed` and a "Retry" button within one minute after the time limit.
- **SC-007**: A person can follow the state of any pipeline from the thread alone, without other tools.
- **SC-008**: The routing, trust, plan check, and claim rules run in unit tests without Slack and without an LLM.
- **SC-009**: In 100% of tests, a step that another person started loads only exposed capabilities, gets no file tool, and cannot call an `owner-only` tool.
- **SC-010**: The metrics script gives the correct values for a test channel with known threads.
- **SC-011**: In 100% of builds, no pipeline core module imports a runtime-specific module, and no pipeline core module holds a runtime tool name or a plugin, skill, MCP, wiz-review, or GitLab term (import-boundary test).
- **SC-012**: In 100% of tests, the mention of the next agent comes from the card `bot_user_id`, and the adapter makes no `bots.info` and no `users.info` call.
- **SC-013**: In 100% of tests, a plan with a tag that no trusted card offers is rejected before ✅. A plan with a tag that a card offers is accepted.
- **SC-014**: In 100% of tests with two eligible agents for a tag step, exactly one agent runs the step, and it is the one with the lowest claim `ts`.
- **SC-015**: In 100% of tests, a tag step that nobody claims within the step time limit shows `failed`, `no_claimer`, and a "Retry" button.
- **SC-016**: In 100% of tests, a bad `payload` gives `invalid_payload` with no runtime call, and a bad `data` gives `invalid_result`. A capability with no schema behaves as before.
- **SC-017**: In 100% of tests, a non-owner step for a declared capability that is not exposed runs nothing, and the `exec` child has only the allowed environment variables and `PIPE_RUNTIME=1`.
- **SC-018**: In 100% of tests, an answer from the thread starter or the agent owner resumes the same step on the same agent with no new claim and the same `hop`. An answer from another person changes nothing. A wait over `dialog_timeout_h` gives `failed`, `dialog_timeout`, and a "Retry" button, also after a restart. A wait longer than `step_timeout_min` does not give `timeout`.
- **SC-019**: In 100% of tests, the effective payload of step N holds the `text` and `artifacts` of all done steps before N, in order, cut to the limits. Step 0 has no context keys.
- **SC-020**: In 100% of tests, a gated step or a step with a proposal blocks the next step until a new ✅ from an allowed person. A proposal that fails `validate_plan` gives `invalid_proposal`. No proposal starts a step.
- **SC-021**: In 100% of tests, a claim from an agent that holds an excluded step is ignored, and a plan with no possible claimer after the exclusion is rejected when this can be proved.
- **SC-022**: In 100% of tests, the `on_fail` branch happens only for `run_failed`, at most once, and the flow ends after the branch step. A plan with two `on_fail` fields, a branch target that is not last, or a human step with `on_fail` is rejected.
- **SC-023**: In 100% of tests, the `hop` limit is 5 only when the declared template source is verified (same name, same hash, matching steps) on the adapter. A forged, stale, or unknown source gives the limit 3 and the text `hop limit exceeded (plan source not verified)`.
- **SC-024**: In 100% of tests, a message with a `flow:` word and one agent is a pipeline request (`plan_flow`, no runtime call). A planner output with `flow` and `steps` uses the template only. No code path writes a template file.
- **SC-025**: In 100% of builds, the import-boundary test passes for every module in `src/pipe/core/` (also `source.py`, and the modules of specs 005 and 006), and no core module holds a standard tag name.
- **SC-026**: In 100% of tests, a rejected `write` tag step ends `failed`, `rejected`, with no second claimer and no "Retry".

## Assumptions

- Specs 001 and 002 exist. Agent cards are in `#pipe-agents`.
- Pipelines run in `#pipe-work`. One thread is one task.
- Agents have no coordinator and no database. The thread messages hold the state.
- The step time limit comes from the config. The default is 30 minutes.
- "Owner offline" means that the owner's adapter does not take the step.
- A dialog answer must mention the agent (decision N1), because the Slack adapter reads only mentions (`app_mention`, spec 001). The question text says so.
- Delegation to another owner's repo (spec 004) and the review capability and triggers (spec 005) are not part of this feature. This feature supports `read` steps and `approve` steps (the human step). A review step is a normal `read` step whose capability has the tag `review`. The core has no review code.
- A declared capability (spec 002) supports `access: read` only in this version. A tag step with `access: write` can bind only to a capability that has no declared access (a `claude` capability).
- The owner should set `max_budget_usd` (runtime adapter key from 001). A step that another person started spends the budget of the owner. This feature adds no owner gate for such a step (decision Q6 in plan.md).

## Notes for /speckit-plan

- `pipe.task.v1` metadata (design brief §5.2).
- Pure functions: `route(event, thread_state) -> decision`, `validate_plan(plan, cards, starter, flows) -> errors`, `resolve_claim(claims) -> winner`, `build_run_request(step, starter, owner) -> RunRequest`.
- The core uses `capability_id` values from the cards only. The `claude` runtime adapter maps `RunRequest` to flags. Add an import-boundary test (constitution principle XI).
- Step timeout from `step_timeout_min`.
- Trust rules from design brief §8.
- Write the unit tests first (constitution principle VII).
- Catch-up and dedupe are reused from spec 001.
- New pure functions: `matches_tag`, `bind_step`, `access_fits`, `pick_runtime`, `check_input`, `check_output`, and the schema validator of spec 002 (`core/schema.py`).
- Second batch (2026-11-26): `effective_source`, `hop_limit` (`core/source.py`); `claim_excluded`, `exclusion_deadlock`, `branch_target`, `next_step`, `gate_pending`, `open_question`, `dialog_expired`, `flow_word`, and `effective_payload` (existing core modules); `validate_plan(plan, cards, starter, flows)`. New runtime adapters: `runtime_exec`, `runtime_http`, and the selector `runtime_select`.
