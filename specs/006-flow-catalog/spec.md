# Feature Specification: Flow Catalog

**Feature Branch**: `006-flow-catalog`

**Created**: 2026-11-26

**Updated**: 2026-11-26 (pass 2: aligned with constitution v1.3.0 and the second batch of spec 003; owner decisions DQ1 to DQ12 confirmed)

**Status**: Draft

**Input**: User description: "The team keeps flow templates as files. A person starts a template with `@agent flow:<name> <goal>`, or the planner picks a template from the free text. A template has only tag steps. A plan from a template still needs approval. Ten flows are in version 1: feature-dev, bugfix, planning, brainstorm, research, test-run, troubleshoot, review-handoff, delegate, and nightly."

## Model (from specs 001 to 005 and the design brief)

- A step is `{agent | "any", capability | "tag:<tag>", access: read|write|approve, goal, payload?, target?, exclude_agents_of?: [<step>]}`. A step with `agent: "any"` is a tag step. Any agent whose card has an exposed capability with that tag can claim it. The claim with the lowest `ts` wins (spec 003).
- `pipe.task.v1` uses `phase`, `access`, and `next: {agent, access, payload}`.
- The `Transport` port hides the chat product. Slack is the first transport. `upload_file` sends artifacts such as screenshots and reports.
- The owner can declare capabilities in the config (`exec`, `http`). The config map `tags` gives tags to any capability (spec 002). A capability can have an `input_schema` and an `output_schema`.
- A slow capability is a wrapper that polls. It applies to any long task, for example e2e tests (spec 005, `contracts/slow-capability.md`).
- A dialog step can return `status: waiting` with `reason: needs_input` and a question. A human reply in the thread resumes the same step on the same agent, with the thread context. `hop` does not grow.
- The next step gets the `text` summary and the `artifacts` of all previous steps in its payload. Large context goes by link.
- A step can return a proposed plan. The proposal passes `validate_plan` and goes to `needs_approval` (✅). A step never starts work by itself.
- Steps run one by one. The MVP has no parallel steps.
- The core functions `effective_source`, `hop_limit`, `parse_source`, `claim_excluded`, `exclusion_deadlock`, `branch_target`, `next_step`, `gate_pending`, `open_question`, `dialog_expired`, `step_rejected`, and `flow_word` are spec 003 functions. `pipeline.source` is `free` or `template:<name>@<32 hex>`. The LLM never writes it. The planner output may have `flow` (at most 32 characters). When `flow` is set, `steps` are ignored.
- The core is capability-, runtime-, and transport-agnostic (constitution XI). It knows no tag name, no plugin, no review tool, no GitLab, and no Slack.

## What this feature adds

1. Flow templates: files `flows/<name>.yaml` (shared, in git) and `~/.pipe/flows/<name>.yaml` (owner override).
2. A standard tag vocabulary: the file `flows/tags.yaml`.
3. The mention syntax `@agent flow:<name> [key=value ...] <goal>`.
4. A pure template check and a pure template expansion. The result is a normal plan.
5. A plan source (`template:<name>@<hash>` or `free`). The source sets the `hop` limit: 5 for a verified template, 3 for a free plan.
6. Data and rules on top of spec 003: the template files, the tag vocabulary, the mention parser, and the expansion. The three small step fields `exclude_agents_of`, `gate: approval`, and `on_fail`, the plan source, and the `hop` limit by source are defined and implemented in spec 003 (`core/source.py` and `core/pipeline.py`). Spec 006 only uses them.
7. Ten flows (the catalog of version 1).

## Scope notes

- A flow is a plan with a name. It adds no new message type, no new status, and no new trust path.
- This feature relaxes FR-021 of spec 003. Templates from git are allowed. **Saving pipelines from chat stays forbidden.** No chat command, no mention, no button, and no agent run writes a file in `flows/` or in `~/.pipe/flows/`. The owner edits template files by hand.
- Status sync (flow B in the design brief) is not a flow. It runs from hooks (spec 001). No template covers it.
- Templates never name a concrete agent, plugin, skill, MCP server, or tool. They name tags.
- A template has no loop. It is linear. It has at most one conditional step.

## User Scenarios & Testing *(mandatory)*

Each flow scenario states: the goal, the steps (tag and access), the needed tags, the gates, the expected artifacts, the failure and timeout behaviour, and an acceptance test. An acceptance test runs the planner path with fake cards and a `FakeTransport`. It uses no LLM (`validate_plan` plus template expansion), unless it says "manual check". The exact template files are in [contracts/flow-catalog.md](contracts/flow-catalog.md).

**Common rules for all flows (not repeated below).**

- Gates: the plan from a template needs ✅ from the thread starter or the owner of the planner (spec 003). A thread that a trigger bot started follows spec 005 (allowlist or the owner button). Every `write` step meets the owner gate of spec 004. A template adds no bypass to any gate.
- Failure: a step that ends with an error is `failed` with a reason and a "Retry" button (spec 003). The system never retries by itself. A step that exceeds `step_timeout_min` is `failed` with `reason: timeout` and a "Retry" button. When no agent claims a tag step, the sender posts `failed` with `reason: no_claimer` (spec 003).
- Context: each step gets the `text` and the `artifacts` of all previous steps in its payload.
- Missing tags: when no trusted card offers a tag that the template needs, the plan is rejected before ✅. The error lists the missing tags by name.
- Hop: the number of agent steps in the template is at most 5. A verified template has `hop` limit 5.

### User Story 1 - Start a flow by name (Priority: P1)

A person writes `@coder-pavlo flow:bugfix the login page returns 500`. The agent `coder-pavlo` is the planner. It loads the template `bugfix`, checks it, and expands it into a plan. It posts the plan with the status `needs_approval`. No LLM runs. After ✅, the pipeline starts.

**Why this priority**: Every flow needs this path.

**Independent Test**: Put the template file in a temporary directory. Give the planner fake cards. Post the mention. Check the plan message, the source, and that no runtime call happened.

**Acceptance Scenarios**:

1. **Given** the template `bugfix` exists and every tag has a card, **When** the mention arrives, **Then** the planner posts a plan with `source: template:bugfix@<hash>` and the status `needs_approval`. No runtime call happens.
2. **Given** a template named `bugfix` exists in the git directory and in `~/.pipe/flows/`, **When** the planner loads it, **Then** the override wins.
3. **Given** the name `flow:nope` has no template, **When** the mention arrives, **Then** the planner posts a rejected plan (`failed`) with the text `flow nope not found` and the list of known flow names.
4. **Given** no trusted card offers the tags `e2e` and `review`, **When** the planner expands `feature-dev`, **Then** it posts a rejected plan whose reason is `flow feature-dev: missing tags: e2e, review`. No ✅ can start it.
5. **Given** the message names one agent and `flow:bugfix`, **When** the planner reads it, **Then** the message counts as a pipeline request (the `flow:` word replaces the second agent mention of spec 003).
6. **Given** the message has no `flow:` word and the text matches a template, **When** the planner runs the LLM, **Then** the LLM may return only a template name. The core expands it (manual check for the choice, see DQ4).
7. **Given** a template file is invalid, **When** the planner loads templates, **Then** it skips that file, reports the error in `pipe flows`, and loads the others.
8. **Given** a person writes "save this plan as a flow", **When** the planner reads it, **Then** it writes no file. It answers with a normal chat reply.

---

### User Story 2 - A plan records its source, and the source sets the hop limit (Priority: P1)

A plan has a `source`: `template:<name>@<hash>` or `free`. Every adapter works out the effective source itself. A plan has the template source only when the template file on that adapter has the same hash and the plan steps match the template. Only then does the `hop` limit equal 5. In every other case it equals 3.

**Why this priority**: This is a security point. A plan must not raise its own limit by a claim.

**Independent Test**: Run the pure functions `effective_source` and `hop_limit` with a template and with changed plans. Run `route` with a handoff that has `hop` 4.

**Acceptance Scenarios**:

1. **Given** a plan declares `template:feature-dev@H` and the local file has hash `H` and the steps match, **When** an adapter reads the handoff with `hop` 4, **Then** it accepts it.
2. **Given** the same plan, **When** the handoff has `hop` 6, **Then** the adapter refuses it (`hop limit exceeded`).
3. **Given** a plan declares `template:feature-dev@H` and the local hash differs, **When** the handoff has `hop` 4, **Then** the adapter refuses it. The effective source is `free`.
4. **Given** a plan declares a template and a person changed a step before ✅ (a tag, an access, an order, or the number of steps), **When** an adapter checks it, **Then** the effective source is `free`.
5. **Given** a plan declares a template and only a `goal` text differs from the expansion, **When** an adapter checks it, **Then** the effective source is the template.
6. **Given** a plan declares `free` and has 4 agent steps, **When** `validate_plan` runs, **Then** it is invalid (limit 3).
7. **Given** a plan declares a template that the adapter does not have, **When** the adapter checks it, **Then** the effective source is `free`.
8. **Given** a bot with a card posts a plan that declares a template but has 5 other steps, **When** the next adapter checks it, **Then** the effective source is `free`, and the limit is 3.

---

### User Story 3 - feature-dev (Priority: P1)

**Goal**: Build a feature from a request to a merged change.

**Steps**:

| # | Step id | Tag | Access | Notes |
|---|---|---|---|---|
| 1 | decompose | `tag:decompose` | read | Returns a task proposal. `gate: approval`. |
| 2 | implement | `tag:implement` | write | Works in a worktree. Result: an MR. |
| 3 | e2e | `tag:e2e` | read | Runs end-to-end tests on the branch. |
| 4 | review | `tag:review` | read | `exclude_agents_of: [implement]`. |
| 5 | approve | human (the starter) | approve | A button. |

**Needed tags**: `decompose`, `implement`, `e2e`, `review`.

**Gates**: ✅ on the plan. ✅ on the proposal of step 1 (`gate: approval`). The 004 gate for step 2 when the agent has another owner. The trigger allowlist when a trigger bot started the thread. The final approval button.

**Artifacts**: the task proposal (step 1), the MR link (step 2), the test report and screenshots through `upload_file` (step 3), the review drafts link (step 4).

**Failure and timeout**: any failed step stops the flow with a "Retry" button. A step 3 failure does not branch. A review by the agent that did the implementation is not possible (`exclude_agents_of`). When no other agent offers `review`, the step ends `failed` with `reason: no_claimer`.

**Acceptance test**: With fake cards for four tags and two agents, the expansion gives 4 agent steps and 1 human step, source `template:feature-dev@<hash>`, and the exclusion `review` excludes `implement`. After step 1 is `done`, no handoff goes out before ✅. A fake agent that claimed step 2 cannot claim step 4.

**Acceptance Scenarios**:

1. **Given** step 1 posts `done` with a proposal, **When** the core reads the thread, **Then** the thread shows `needs_approval` and step 2 does not start.
2. **Given** ✅ comes from the thread starter, **When** the core reads it, **Then** the handoff for step 2 is posted once.
3. **Given** ✅ comes from another person, **When** the core reads it, **Then** nothing changes.
4. **Given** agent A claimed `implement`, **When** A tries to claim `review`, **Then** the claim is ignored.
5. **Given** the hop count reaches 4 and the source is verified, **When** the handoff is read, **Then** it is accepted.

---

### User Story 4 - bugfix (Priority: P1)

**Goal**: Fix a bug with a proof by test.

**Steps**: `reproduce` (read, `tag:reproduce`: returns the code of a failing test in its reply) → `implement` (write: adds that test, fixes the bug, opens an MR) → `e2e` (read) → `review` (read, `exclude_agents_of: [implement]`) → `approve` (human).

**Needed tags**: `reproduce`, `implement`, `e2e`, `review`.

**Trigger**: chat, or an issue. For an issue, a trigger bot posts `flow:bugfix <issue text>` (spec 005, DQ3; the trigger carries `flow:<name> <goal>` and no `pipeline`).

**Gates**: ✅ on the plan (or the trigger gate), the 004 gate for `implement`, the final approval button.

**Artifacts**: the failing test code from the `reproduce` reply (target file path, test code, expected failure), the MR, the test report, the review drafts.

**Failure and timeout**: when `reproduce` cannot make a failing test, it ends `failed` with a reason and a "Retry" button. The flow does not go on. This is the proof rule: no fix without a failing test. `reproduce` does not run the test and does not change files. `implement` gets the full reply in the thread.

**Acceptance test**: Expand `bugfix` with fake cards. Check 4 agent steps, the tags, the access values, and the exclusion. Post a trigger message whose text has `flow:bugfix`. Check the plan from the template and the trigger gate decision (allow or ask).

**Acceptance Scenarios**:

1. **Given** a trigger bot in the allowlist posts `flow:bugfix <text>`, **When** the planner reads it, **Then** the planner expands the template, posts the plan, and starts without ✅ (spec 005 rule).
2. **Given** the trigger bot is not in the allowlist, **When** the planner reads it, **Then** the owner gets the accept/reject button.
3. **Given** `reproduce` ends `failed`, **When** the core reads the thread, **Then** `implement` does not start.

---

### User Story 5 - test-run (Priority: P2)

**Goal**: Run end-to-end tests on a branch or an environment and show the proof.

**Steps**: `e2e` (read, `tag:e2e`, `on_fail: troubleshoot`) → `troubleshoot` (read, `tag:troubleshoot`, runs only when step 1 fails).

**Needed tags**: `e2e`, `troubleshoot`.

**Trigger**: chat, a schedule, or an MR event.

**Gates**: ✅ on the plan (or the trigger gate). No `write` step.

**Artifacts**: the e2e report and the screenshots, sent with `Transport.upload_file` and linked in `artifacts`. On failure: the diagnosis text.

**Failure and timeout**: when `e2e` ends `failed` with `reason: run_failed`, the claimant posts the branch handoff to `troubleshoot`. The flow ends after `troubleshoot`. When `e2e` ends with `timeout`, `no_claimer`, or `invalid_payload`, the flow does not branch. It shows `failed` and a "Retry" button.

**Acceptance test**: Expand `test-run`. Check that step 2 is the `on_fail` target of step 1 and is the last step. Run `branch_target` with `run_failed` (gives step 2) and with `timeout` (gives none). Run a fake thread: e2e `done` leaves step 2 skipped and the thread `done`.

**Acceptance Scenarios**:

1. **Given** `e2e` succeeds, **When** the core reads the thread, **Then** the thread is `done` and `troubleshoot` never starts.
2. **Given** `e2e` ends `failed` with `run_failed`, **When** the core reads the thread, **Then** `troubleshoot` starts once with the payload of step 1.
3. **Given** `troubleshoot` ends (done or failed), **When** the core reads the thread, **Then** no further step starts.
4. **Given** `e2e` ends with `timeout`, **When** the core reads the thread, **Then** `troubleshoot` does not start.

---

### User Story 6 - troubleshoot (Priority: P2)

**Goal**: Find the cause of an alert or a fault and propose a fix.

**Steps**: `collect` (read, logs, metrics, cluster state through the capabilities that the agent owner exposes) → `diagnose` (read) → `implement` (write: a fix MR) → `approve` (human).

**Needed tags**: `collect`, `diagnose`, `implement`.

**Trigger**: an alert (a trigger bot) or chat.

**Gates**: ✅ or the trigger gate, the 004 gate for `implement`, the final approval button.

**Artifacts**: the collected data as a link or a file (`upload_file`), the diagnosis text, the fix MR.

**Failure and timeout**: when `collect` finds nothing, it ends `done` with the text `no data`. `diagnose` then ends `failed` with a reason. A large log goes by link, not in the thread text.

**Acceptance test**: Expand `troubleshoot` with fake cards. Check 3 agent steps and 1 human step. Check that no tag name enters a core module (boundary test).

**Acceptance Scenarios**:

1. **Given** an alert trigger bot is in the allowlist, **When** it posts `flow:troubleshoot <alert text>`, **Then** the pipeline starts without ✅.
2. **Given** `collect` returns artifacts, **When** `diagnose` starts, **Then** its payload holds those artifacts.
3. **Given** `implement` has another owner, **When** the step starts, **Then** the 004 gate applies.

---

### User Story 7 - review-handoff (Priority: P2)

**Goal**: Review a change, fix the review comments, and review again.

**Steps**: `review` (read) → `implement` (write: fixes from comments) → `review` (read, `exclude_agents_of: [implement]`) → `approve` (human).

**Needed tags**: `review`, `implement`.

**Trigger**: an MR event or chat. The MR link is in the goal or in the payload of the first step.

**Gates**: ✅ or the trigger gate, the 004 gate for `implement`, the final approval button.

**Artifacts**: the review drafts link (steps 1 and 3), the fix commits as an MR update or a new MR (step 2).

**Failure and timeout**: a review is a slow capability. It uses the polling wrapper of spec 005. The step timeout applies. The spec 003 limit of two back and forth passes between two agents applies (FR-010 of 003). The flow is A (review) → B (implement) → A (review): one return. It is allowed.

**Acceptance test**: Expand `review-handoff`. Check that step 3 excludes step 2. Check that the pass pattern A, B, A is not refused by the ping-pong rule.

**Acceptance Scenarios**:

1. **Given** the first review ends, **When** step 2 starts, **Then** its payload holds the drafts link of step 1.
2. **Given** agent B did step 2, **When** B tries to claim step 3, **Then** the claim is ignored.
3. **Given** the second review ends `done`, **When** the core reads the thread, **Then** the approval button appears.

---

### User Story 8 - planning (Priority: P2)

**Goal**: Turn an idea into a spec and a task proposal.

**Steps**: `brainstorm` (read, dialog) → `spec` (write: a document or an MR) → `decompose` (read, task proposal, `gate: approval`).

**Needed tags**: `brainstorm`, `spec`, `decompose`.

**Gates**: ✅ on the plan. The 004 gate for `spec`. ✅ on the task proposal (the end of the flow).

**Artifacts**: the brainstorm summary text, the spec document or MR link, the task proposal.

**Failure and timeout**: the `brainstorm` step can return `waiting` with `reason: needs_input` and a question. A human reply in the thread resumes the same step on the same agent, with the thread context. `hop` does not grow. While the step waits for input, the step timer is paused. When nobody answers within `dialog_timeout_h` (24), the step ends `failed` with `reason: dialog_timeout` and a "Retry" button (DQ7). The answer needs a mention of the agent.

**Acceptance test**: Expand `planning`. With a `FakeRuntime` that returns `needs_input` once, check that the same step resumes after a reply and that `hop` is unchanged. Check that the thread is `needs_approval` after step 3 and `done` after ✅.

**Acceptance Scenarios**:

1. **Given** `brainstorm` returns `needs_input`, **When** a human replies in the thread, **Then** the same agent resumes the same step. No new claim and no `hop` increase happen.
2. **Given** a reply comes from a person who is not the starter or the owner, **When** the core reads it, **Then** the question stays open. An answer needs a mention of the agent, and it counts only from the thread starter or the agent owner (spec 003 N1; DQ7).
3. **Given** step 3 posts a proposal, **When** the core reads the thread, **Then** the thread is `needs_approval` and no work starts.
4. **Given** the proposal is a plan, **When** it fails `validate_plan`, **Then** the step ends `failed` with the errors.

---

### User Story 9 - brainstorm (Priority: P3)

**Goal**: Discuss a topic with the context of repos, docs, and MRs, and keep a summary.

**Steps**: `context` (read: repos, docs, MR) → `brainstorm` (read, dialog) → `summarize` (read: a summary artifact).

**Needed tags**: `context`, `brainstorm`, `summarize`.

**Gates**: ✅ on the plan. No `write` step.

**Artifacts**: the context links, the summary document (`upload_file` or a link).

**Failure and timeout**: as in `planning` for the dialog. A missing context ends `context` with `done` and the text `no context found`. The dialog continues.

**Acceptance test**: Expand `brainstorm`. Check 3 agent steps and no write access. Run the dialog test of US8 on step 2.

**Acceptance Scenarios**:

1. **Given** `context` returns links, **When** `brainstorm` starts, **Then** its payload holds those links.
2. **Given** the dialog ends, **When** `summarize` starts, **Then** its payload holds the `text` of both previous steps.

---

### User Story 10 - research (Priority: P3)

**Goal**: Research a question in the web, docs, and code, and keep a document.

**Steps**: `research` (read: web, docs, code) → `summarize` (read: a document artifact).

**Needed tags**: `research`, `summarize`.

**Gates**: ✅ on the plan. No `write` step.

**Artifacts**: the source links and the final document (`upload_file` or a link).

**Failure and timeout**: a research run can be slow. The step timeout applies. A failed step has a "Retry" button.

**Acceptance test**: Expand `research`. Check 2 agent steps, `read` access, and that the plan passes `validate_plan` with fake cards.

**Acceptance Scenarios**:

1. **Given** the `research` step ends, **When** `summarize` starts, **Then** its payload holds the links of step 1.
2. **Given** the owner of the research agent did not expose the web capability, **When** the plan is built, **Then** the missing tag `research` is reported by name.

---

### User Story 11 - delegate (Priority: P3)

**Goal**: Ask the agent of another owner to change a repo of that owner.

**Steps**: `implement` (write, `tag:implement`) for the agent that the person names. The name comes from the second agent mention.

**Syntax**: `@coder-pavlo @coder-bob flow:delegate add the field X`. The planner is `coder-pavlo`. The second named agent fills the placeholder `$agent`.

**Needed tags**: `implement`.

**Gates**: ✅ on the plan. The 004 gate (allowlist or the button of the owner of `coder-bob`). The merge of the MR by a human.

**Artifacts**: the MR link.

**Failure and timeout**: as in spec 004 (`unknown_target`, `target_required`, `no changes`, and the other reasons). A rejected step has no "Retry" button.

**Acceptance test**: Expand `delegate` with a `$agent` mention. Check that the step has the fixed agent and the lowest capability ID of that card with the tag `implement`. Check that the 004 gate decision is `ask` when the sender is not in the allowlist. Check the error when no second agent is named.

**Acceptance Scenarios**:

1. **Given** the second agent has a capability with the tag `implement`, **When** the plan is built, **Then** the step names that agent and that capability ID. The step is `write`.
2. **Given** the second agent has no such tag, **When** the plan is built, **Then** the plan is rejected. The error says `missing tags: implement` for that agent.
3. **Given** the message has no second agent, **When** the plan is built, **Then** the plan is rejected with `flow delegate needs a second agent mention`.

---

### User Story 12 - nightly (Priority: P3)

**Goal**: Run a regular check from a CI schedule and report the result.

**Steps**: `check` (read, `tag:$check`, `on_fail: troubleshoot`) → `troubleshoot` (read, runs only when step 1 fails). The parameter `check` is `e2e` or `deps-check`. The default is `e2e`.

**Syntax**: `flow:nightly check=deps-check`.

**Needed tags**: the tag of `check`, and `troubleshoot`.

**Trigger**: a CI schedule (a trigger bot, spec 005). The trigger text holds `flow:nightly`.

**Gates**: the trigger allowlist, or the owner button. No `write` step.

**Artifacts**: the report (`upload_file` or a link). On failure: the diagnosis text.

**Failure and timeout**: as in `test-run`. The branch happens only for `run_failed`. A schedule that runs twice starts two threads (spec 005 DQ7).

**Acceptance test**: Expand `nightly` with no parameter (tag `e2e`) and with `check=deps-check`. Check the error for `check=lint`. Check the branch rule as in `test-run`.

**Acceptance Scenarios**:

1. **Given** a trigger bot in the allowlist posts `flow:nightly`, **When** the planner reads it, **Then** the plan uses the tag `e2e` and starts without ✅.
2. **Given** `check=deps-check`, **When** the plan is built, **Then** step 1 uses the tag `deps-check`.
3. **Given** `check=lint`, **When** the plan is built, **Then** the plan is rejected with `flow nightly: bad value for check`.

### Edge Cases

- Two template files have the same `name` in one directory. This cannot happen: the name equals the file name.
- A template file name differs from its `name` field. The file is invalid.
- The override file is invalid and the git file is valid. The planner uses the git file and reports the override error in `pipe flows`. (An invalid override never hides a good template.)
- The git directory is missing. Only the override files load. `pipe flows` says so.
- A template needs a tag that is not in `flows/tags.yaml`. The file is invalid.
- A template needs a tag that the team has, but the card of that agent hides it (not exposed). The tag counts as missing.
- A person edits the plan before ✅ (the planner posts a new plan message). The source of the new message is `free`. The old plan message is not used.
- A forged plan message declares a template. Every adapter works out the source again. The claim has no effect on its own.
- Two team members have different git versions of a template. The hashes differ. The adapter with the other version works out `free`. The thread fails at `hop` 4 with a clear text. Both people update their copy.
- A flow runs while the template file changes on disk. The plan holds the expansion. The new file changes only the verification of later handoffs, so a changed file turns the source into `free`. The owner must not edit a template while a flow runs.
- The planner agent has an override template with a new hash. The other adapters do not have it. The source is `free` for them. The override is a personal template.
- A goal text holds a `flow:` word. Only the first `flow:` token that starts a word counts.
- `flow:<name>` appears inside a quoted or code block of the message. It still counts (the parser does not read the markup).
- A template step has `on_fail` and the step is already the last step. The file is invalid.
- A free plan has `on_fail`, `gate`, or `exclude_agents_of`. The same structure rules apply. The `hop` limit is 3.
- The `exclude_agents_of` rule leaves no eligible agent. Plan check: if the only agent that can claim step N is certainly the claimant of an excluded step, the plan is invalid. Else the step ends `no_claimer` at run time.
- The agent of an `implement` step has a branch that the review agent cannot read. This is outside the core (it is a capability matter).
- A trigger message has both `pipeline` and a `flow:` text. The message is ignored (`bad_payload`).

## Requirements *(mandatory)*

### Functional Requirements

**Template files**

- **FR-001**: The system MUST read flow templates from files `flows/<name>.yaml`. The shared files MUST be in the team git repository (`flows/`). An owner override MUST be in `~/.pipe/flows/<name>.yaml`. A file in the override directory MUST win over the git file with the same name. The path of the shared directory MUST come from the optional config key `flows_dir`. The default is `flows/` in the checkout.
- **FR-002**: A template step MUST use `agent: any` with `capability: "tag:<tag>"`, or one of the placeholders `$agent` (a step agent that the message names) and `$starter` (a human step for the thread starter). A template MUST NOT name a concrete agent, plugin, skill, tool, URL, local path, or token. `validate_flow` MUST reject such a file.
- **FR-003**: A template MUST follow [contracts/flow-template.md](contracts/flow-template.md). It has 1 to 5 agent steps and at most 1 human step. The human step is the last step. It has at most one `on_fail`. It has no loop.
- **FR-004**: The loader MUST use `yaml.safe_load`. It MUST refuse a file larger than 20 000 bytes. It MUST report an invalid file and load the others. It MUST NOT write any file in a template directory.
- **FR-005**: The file name (without `.yaml`) MUST equal the `name` field. A name matches `^[a-z0-9-]{1,32}$`.

**Use**

- **FR-006**: A person MUST be able to start a flow with `@agent flow:<name> [key=value ...] <goal>` ([contracts/flow-mention.md](contracts/flow-mention.md)). The first agent named is the planner. A message with a `flow:` word MUST count as a pipeline request, also when it names one agent.
- **FR-007**: The planner MAY pick a template from the free text. In that case the LLM MUST return only a template name, and the core MUST expand the template. The LLM MUST NOT write steps for the template path (DQ4).
- **FR-008**: The expansion MUST be a pure function of the template, the goal, the parameters, the cards, the starter, and the mentions. It MUST NOT call an LLM.
- **FR-009**: A plan from a template MUST pass `validate_plan` (spec 003) and MUST need ✅ from the thread starter or the owner of the planner. A thread that a trigger bot started MUST follow the gate rules of spec 005. A `write` step MUST meet the owner gate of spec 004. A template MUST NOT bypass a gate.
- **FR-010**: This feature relaxes FR-021 of spec 003: templates from git (and from the owner override) are allowed. The system MUST NOT save a pipeline from chat. No chat message, no button, and no agent run MAY write a template file.
- **FR-011**: When a template needs a tag that no trusted card offers (exposed, with a fitting access), the planner MUST reject the plan before ✅. The error MUST list all missing tags by name: `flow <name>: missing tags: <tag>, <tag>`.
- **FR-012**: The owner MUST map capabilities to tags with the config map `tags` (spec 002). This feature adds no other way to tag a capability.

**Tags**

- **FR-013**: The standard tag vocabulary MUST be the data file `flows/tags.yaml`: for each tag, a short meaning and a default access ([contracts/tag-vocabulary.md](contracts/tag-vocabulary.md)). The core MUST receive the vocabulary as data. No core module MAY hold a tag name.
- **FR-014**: A template MUST use only tags from the vocabulary. The `access` of a step MUST equal the default access of its tag. When a step has no `access`, the default applies.

**Structure**

- **FR-015**: A template MUST have at most one step with `on_fail: <step id>`. The target MUST be a later step and the last step. The target MUST run only when the source step fails. The flow MUST end after the target. A template MUST NOT have a loop or a jump back.
- **FR-016**: The branch MUST happen only when the source step ends `failed` with `reason: run_failed`. `run_failed` is only a runtime result with `status: failed`. A non-zero exit of an `exec` capability gives `RuntimeFailed` and does not branch. An e2e or slow wrapper MUST print `{status: failed}` and exit with code 0 to take `on_fail` (spec 005 `contracts/slow-capability.md`). A timeout, `no_claimer`, `invalid_payload`, `invalid_result`, `rejected`, and a hop refusal MUST NOT branch (DQ5).
- **FR-017**: A step MAY have `exclude_agents_of: [<step id>]`. The ids MUST name earlier steps. In the plan they become step indexes. A claim from an agent that holds the winning claim of an excluded step MUST be ignored.
- **FR-018**: A step MAY have `gate: approval`. After that step is `done`, the thread MUST be `needs_approval`. The next step MUST NOT start before ✅ from the thread starter or the owner of the planner (the trigger owner rule of spec 005 for a trigger thread). A `gate: approval` on the last step MUST end the flow only after ✅.
- **FR-019**: Steps MUST run one by one. A template MUST NOT have a parallel step.

**Source and hop**

- **FR-020**: A plan MUST record its source in `pipeline.source`: `template:<name>@<hash>` or `free`. The hash is the first 32 hex characters of the SHA-256 of the canonical JSON of the parsed template ([contracts/plan-source.md](contracts/plan-source.md)).
- **FR-021**: Every adapter MUST work out the effective source itself with the pure function `effective_source` of spec 003 (`core/source.py`). The declared source is only a claim. The effective source is `template` only when (1) the adapter has a template of that name, (2) its hash equals the declared hash, and (3) the plan steps match the template shape. In every other case it is `free`.
- **FR-022**: The `hop` limit MUST be 5 for a plan with the effective source `template`, and 3 for `free` (`hop_limit`, `MAX_HOP_FREE`, `MAX_HOP_TEMPLATE` of spec 003). The planner (`validate_plan(plan, cards, starter, flows)`) and every receiver (`route`) MUST use the effective source. This is a rule of constitution 1.3.0, not a deviation. Spec 006 supplies the template data and `Flow.hash` and `Flow.matches(steps, cards, starter)` (the shape check) to those functions.
- **FR-023**: A plan that a human changed before ✅ MUST have the source `free`. The planner MUST write `free` in the new plan message.
- **FR-024**: The text of a hop refusal MUST say when the cause is an unverified template: `hop limit exceeded (plan source not verified)`.

**Context, artifacts, dialog**

- **FR-025**: A flow MUST rely on the context rule: the payload of each step holds the `text` and the `artifacts` of all previous steps (spec 003 and 005 change). Large context MUST go by link.
- **FR-026**: A flow step MAY send artifacts such as screenshots and reports with `Transport.upload_file`. The core MUST carry only the returned links in `artifacts`.
- **FR-027**: A step that returns `waiting` with `reason: needs_input` MUST resume on the same agent after a human reply. `hop` MUST NOT grow. The step timer MUST pause while the step waits. After `dialog_timeout_h` (default 24, 1 to 168), the step MUST end `failed` with `reason: dialog_timeout` and a "Retry" button. An answer MUST mention the agent and MUST come from the thread starter or the agent owner (spec 003 N1).
- **FR-028**: A step MAY return a proposed plan. The proposal MUST pass `validate_plan` and MUST go to `needs_approval`. A step MUST NOT start work by itself. A proposal is context only, in a template and in a free plan (spec 003 N3, U2 = a, DQ12). It never replaces the remaining steps. The plan source does not change.

**Catalog**

- **FR-029**: The repository MUST have the ten files of the catalog of version 1 in `flows/`: `feature-dev`, `bugfix`, `planning`, `brainstorm`, `research`, `test-run`, `troubleshoot`, `review-handoff`, `delegate`, and `nightly`. Each MUST pass `validate_flow` and MUST expand to a valid plan with fake cards that offer all its tags.
- **FR-030**: Status sync MUST NOT be a flow. It runs from hooks (spec 001).

**Tools and boundary**

- **FR-031**: The system MUST provide `pipe flows [show <name> | validate [<name>]]` (spec 001 owns the dispatch with `flows_handler(action, name)`). The list shows templates with name, origin (git or override), hash, the needed tags, and the missing tags for the cards in `#pipe-agents`. `show` prints one template. `validate` checks all templates, or one, and prints the errors. All forms report invalid files and write nothing.
- **FR-032**: The new core module `core/flows.py` MUST be pure and MUST hold only the template data rules: `validate_flow`, `parse_flow`, `flow_hash`, `Flow` (with `hash` and `matches`), `parse_flow_mention`, `missing_tags`, `expand_flow`, `build_plan`, and the tag vocabulary checks. It MUST NOT define a second copy of a spec 003 function. It MUST NOT read files, import a chat product, or name a tag, plugin, review tool, or GitLab. The import-boundary test of spec 003 MUST cover it.
- **FR-033**: No template, test, or file of this feature MAY hold a token, an MCP URL, or a local path.
- **FR-034**: A trigger bot MAY start a flow with the text `flow:<name> <goal>` and no `pipeline` (spec 005 DQ3). The route sends it to `plan_flow` (no LLM call). A trigger message that has both a `pipeline` and a `flow:` word, or neither, MUST be ignored (`bad_payload`).

### Key Entities

- **Flow template**: A file with a name, a description, optional parameters, and linear steps with tags.
- **Tag vocabulary**: The list of standard tags with a meaning and a default access.
- **Plan source**: `template:<name>@<hash>` or `free`. The declared value is a claim. The effective value is worked out by each adapter.
- **Effective source**: The result of `effective_source`: `template` or `free`.
- **Branch step**: The last step of a template. It runs only when its source step fails with `run_failed`.
- **Approval gate**: A step flag. The flow waits for ✅ after that step.
- **Flow mention**: `flow:<name>` and optional `key=value` words in a message.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tests, each of the ten catalog files passes `validate_flow` and expands to a valid plan with fake cards. No LLM runs.
- **SC-002**: In 100% of tests, a plan with no card for a needed tag is rejected before ✅, and the error lists all missing tags by name.
- **SC-003**: In 100% of tests, a plan from a template starts only after ✅ (or the spec 005 trigger gate). A `write` step meets the spec 004 gate.
- **SC-004**: In 100% of tests, the `hop` limit is 5 only when the hash and the shape match. A forged, changed, or unknown source gives the limit 3.
- **SC-005**: In 100% of tests, a human edit of the steps gives the source `free`. A change of a goal text only keeps the template source.
- **SC-006**: In 100% of tests, an `on_fail` branch happens only for `run_failed`, and only once. The flow ends after the branch step.
- **SC-007**: In 100% of tests, an agent that claimed an excluded step cannot claim the excluding step.
- **SC-008**: In 100% of tests, a gated step blocks the next step until ✅ from an allowed person.
- **SC-009**: In 100% of tests, a dialog reply resumes the same step on the same agent and `hop` does not grow.
- **SC-010**: In 100% of builds, the import-boundary test passes with `core/flows.py`: no tag name, no review tool, no GitLab, and no chat product.
- **SC-011**: In 100% of tests, no code path writes a file in a template directory.
- **SC-012**: In 100% of tests, an override file wins by name, and an invalid override does not hide a valid git file.
- **SC-013**: No new file of this feature holds a token, an MCP URL, or a local path.
- **SC-014**: In 100% of tests, `core/flows.py` defines none of the spec 003 functions listed in the Model section.
- **SC-015**: In 100% of tests, a dialog that ends without an answer gives `failed` with `reason: dialog_timeout` and a "Retry" button.

## Assumptions

- Specs 001 to 005, the brief, and the constitution (1.3.0) hold the model changes that this feature uses (pass 1 and pass 2 of 2026-11-26). [plan.md](plan.md) lists the few items that remain. The model changes are: the claim exclusion, the approval gate, the failure branch, the plan source and the variable `hop` limit, the dialog resume, the plan proposal, the context rule for all previous steps, `Transport.upload_file`, and a `flow:` text in a trigger message.
- The team keeps one git repository with `flows/`. Each team member pulls it. A stale copy gives the source `free` and a clear refusal text.
- The planner owner chooses the override carefully. An override is a personal template.
- A capability that the owner declares in the config (`exec`, `http`) has `access: read` only (spec 002). So a tag with default access `write` (`implement`, `spec`) is offered by a `claude` runtime capability only. A template that needs such a tag gets it as a missing tag when no such card exists.
- The tag vocabulary is small. A new tag needs a git change in `flows/tags.yaml`.
- The project already uses `pyyaml` (constitution principle IX). This feature adds no dependency.

## Notes for /speckit-plan

- One new core module: `core/flows.py` (pure). A thin loader outside the core reads the files.
- Reuse the plan check, claim, gate, timeout, Retry, and trigger rules of specs 003 to 005.
- Most of the work is data (ten YAML files) and tests.
- Write the unit tests first (constitution principle VII).
