# Feature Specification: Delegation

**Feature Branch**: `004-delegation`

**Created**: 2026-11-25

**Updated**: 2026-11-26 (pass 2: aligned with constitution v1.3.0 and with spec 003 second batch N1 to N13; owner decisions DQ1 to DQ9 applied)

**Status**: Draft

**Input**: User description: "My agent can ask the agent of a colleague to do work in the colleague's repo. If my agent is in the colleague's allowlist, the work starts at once. If not, the colleague gets a button to accept or reject. The colleague's agent works in a separate branch and opens an MR. The MR link comes back to the thread."

## Model (from specs 001 to 003)

- A step is `{agent, capability, access, goal}`. `agent` may be `any` with `capability: tag:<tag>` (spec 003 late binding). `access` is `read`, `write`, or `approve`. A step can have an optional `payload`. A `write` step can also have an optional `target` (an opaque name of a repo, FR-019).
- A delegation is a step with `access: write` that goes to an agent of another owner. It is not a step type. The core has no field `kind` and no field `skill` for a step.
- The task message is `pipe.task.v1`. It has `phase` (`plan` or `step`), `access`, and `next: {agent, access, payload}`.
- Message types (spec 003 `contracts/task-metadata.md`). The owner gate of this spec uses type 4 (the claim message) with `status: needs_approval`. The buttons are `pipe_accept` and `pipe_reject`. Type 5 `needs_approval` is a different thing: it is the `gate: approval` step field or a plan proposal of spec 003. A type 5 gate has a ✅ release and no button. This spec says "owner gate" for type 4 and never changes type 5, type 10, or type 11.
- The core stays capability-agnostic (constitution principle XI). The core sees a `write` run request and an MR link in `artifacts`. Only the `claude` runtime adapter knows the worktree, git, the directory flags, the deny rules, and the creation of the MR. The MR provider is replaceable. GitLab is the first provider.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Delegate to an allowlisted sender (Priority: P1)

A pipeline has a `write` step for agent B. B has another owner than the person who started the pipeline. The agent that hands over the step is in the allowlist of owner B, and the person who started the pipeline is the owner of that agent or is in the allowlist too (DQ2). The work starts at once, without a button. Agent B works in a separate worktree and branch. The result is an MR. The MR link comes back to the thread.

**Why this priority**: This is the main value of the project: agents of different owners do useful work together.

**Independent Test**: Put the sender in the allowlist of B. Start the pipeline with the owner of the sender. Run a pipeline with a `write` step for B. Check that no button appears and that an MR link appears in the thread.

**Acceptance Scenarios**:

1. **Given** the sender is in the allowlist of agent B, **When** the `write` step reaches agent B, **Then** the work starts without a button.
2. **Given** the work is done, **When** agent B finishes, **Then** the result is an MR from a separate branch and the MR link is in `artifacts` of the thread.
3. **Given** the work runs, **When** agent B changes files, **Then** `main` is never changed.
4. **Given** the person who started the pipeline is the owner of agent B, **When** the `write` step reaches agent B, **Then** the work starts without a gate. The work still runs in a worktree and ends in an MR.

---

### User Story 2 - Ask the owner when the sender or the starter is not trusted (Priority: P1)

The sender is not in the allowlist of owner B, or the thread starter is not trusted (DQ2). Owner B gets an accept/reject button in the thread. After accept, the work starts. After reject, the step gets `status: failed` with `reason: rejected`.

**Why this priority**: Owner B must control who uses the agent and the repo.

**Independent Test**: Send a `write` step from a sender that is not in the allowlist. Check that a button appears and that no work starts before the click.

**Acceptance Scenarios**:

1. **Given** the sender is not in the allowlist of agent B, **When** the `write` step reaches agent B, **Then** owner B gets a button and no work starts.
2. **Given** the button is shown, **When** owner B accepts, **Then** the work starts.
3. **Given** the button is shown, **When** owner B rejects, **Then** the step gets `status: failed` and `reason: rejected`, and no work runs.
4. **Given** the button is shown, **When** a person other than owner B clicks it (the thread starter too), **Then** nothing changes.
5. **Given** the sender is in the allowlist of agent B, **When** the thread starter is neither the owner of the sender nor in the allowlist, **Then** owner B gets a button and no work starts (DQ2).
6. **Given** the sender is in the allowlist and the thread starter is the owner of the sender or is in the allowlist, **When** the `write` step reaches agent B, **Then** the work starts without a button.
7. **Given** a step was rejected, **When** the requester wants the work again, **Then** the step has no "Retry" button and the requester starts a new thread (DQ7).

---

### User Story 3 - Keep foreign work safe (Priority: P2)

The adapter limits what the runtime can do in a `write` step. The runtime works in a separate worktree. It reaches only the files of that worktree. It never pushes to `main`. The worktree is removed after the step.

**Why this priority**: A foreign task must not damage the repo or use the credentials of the owner.

**Independent Test**: Run a delegation. Check the worktree, the branch, the tool limits, the `main` branch, and that the worktree is gone.

**Acceptance Scenarios**:

1. **Given** a `write` step starts, **When** the runtime starts, **Then** it works in a separate worktree and branch of the target repo that the `target` rules select (FR-019, FR-020).
2. **Given** a capability is `owner-only`, **When** a `write` step runs, **Then** the runtime cannot use that capability.
3. **Given** a delegation is done, failed, or timed out, **When** the step ends, **Then** `main` has no new commit from the agent and the worktree is removed.
4. **Given** the runtime changes no file, **When** the step ends, **Then** the step is `failed` with a reason and no MR exists.

### Edge Cases

- A `write` tag step is won by an agent whose owner rejects it. The step ends `failed`, `rejected`, with no "Retry". The other eligible agents do not get a second claim, also after an adapter restart (FR-025, `step_rejected` of spec 003 FR-046).
- A `write` tag step has a bad `payload`. The step fails with `invalid_payload` before any button.

- The sender has no agent card. The metadata is ignored (spec 003).
- The hop count passes the limit of the plan source after a hand-back (3 for a free plan, 5 for a verified template). The step is refused (spec 003 FR-042).
- Owner B is offline. The step gets `waiting` with the reason `owner offline`. The wait time is recorded (spec 003).
- Owner B does not click the button for a long time. The step stays `needs_approval`. A pending button has no expiry (DQ5).
- The step has a `target` that is not in `runtime.claude.delegate_repos` of agent B. The step fails with `reason: unknown_target` before any git command (FR-020).
- The map `delegate_repos` has more than one entry and the step has no `target`. The step fails with `reason: target_required` (FR-020).
- The map `delegate_repos` has exactly one entry and the step has no `target`. The step uses that entry (FR-020).
- The map `delegate_repos` is empty. The agent refuses every `write` step with `reason: repo not available` (FR-020).
- The path of the target repo is not inside the `repo_roots` of agent B, or it is not a git repo. The step fails with a reason before any file change.
- The branch name already exists. The adapter picks a new unique name.
- The runtime ends without changes. There is no MR. The step fails with the reason `no changes`.
- The push works but the adapter cannot get an MR link. The step fails with the reason `no merge request`.
- The step runs longer than the time limit. It fails with a "Retry" button (spec 003). The worktree is removed.
- The owner clicks accept twice, or accept and reject. The first click counts. The step runs at most once.
- The adapter of B restarts while the button is shown. The button still works after the restart.
- The `write` step asks for a capability that is not exposed. The plan check rejects the plan before ✅ (spec 003). If the capability goes away later, the step fails with `capability not available`.
- The runtime result has `status: delegate`. The step fails. Only plan steps start a delegation. The status `delegate` of the runtime contract is reserved and the core ignores it (DQ6).
- A `read` step from another person has no gate. Exposure is the limit. The owner sets `max_budget_usd` to limit the cost (DQ1).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A delegation MUST be a plan step with `access: write` for an agent of another owner. The system MUST NOT add a step type, a field `kind`, or a field `skill`.
- **FR-002**: The plan check MUST accept a bot step with `access: write` when the agent has a card and the card lists the capability of the step (the card lists exposed capabilities only).
- **FR-003**: The receiving adapter MUST apply the card trust, the hop limit, the claim rule, and the exposure check of spec 003 before it applies the owner gate.
- **FR-004**: The owner gate MUST apply to a `write` step when the person who started the pipeline is not the owner of the receiving agent. A step that its own owner started MUST run without a gate.
- **FR-005**: The gate MUST start the work without a click only when both conditions are true: (1) the sender (the bot that hands over the step) is in the allowlist of the owner, and (2) the thread starter is the owner of the sender or is in the allowlist. The thread starter can be a bot ID. A trigger bot (spec 005) that is in the allowlist is a trusted starter. In every other case, the owner gets an accept/reject button, and no work starts before the click. An unknown thread starter gives the button (fail closed, DQ2).
- **FR-006**: Only the owner of the receiving agent MUST be able to accept or reject with the button. A click from any other person, the thread starter too, MUST change nothing.
- **FR-007**: A reject MUST set `status: failed` and `reason: rejected`. A rejected step MUST NOT have a "Retry" button. No work runs.
- **FR-008**: The gate MUST NOT apply to a `read` step. A `read` step keeps the rule of spec 003 (Q6): exposure is the limit. The owner sets `max_budget_usd` (DQ1).
- **FR-009**: The allowlist MUST be in the local config of the receiving agent. Only its owner changes it. It MUST be a list of `sender_id` values (a bot id or a person id). The transport gives the id pattern (Slack: `^[BUW][A-Z0-9]{2,}$`). Spec 005 uses the same list for `kind: trigger` bots.
- **FR-010**: Every `write` step MUST run in a separate git worktree and a separate branch of the target repo. The branch name MUST be unique for each run.
- **FR-011**: The system MUST NOT push to `main`. The system MUST NOT change `main`. The only ref that the adapter pushes is the branch of the step.
- **FR-012**: The result of a delegation MUST be an MR. The MR link MUST come back to the thread in `artifacts`. The MR provider MUST be replaceable. GitLab is the first provider.
- **FR-013**: The runtime of a `write` step MUST reach only the files of its worktree. It MUST get the capability of the step and no `owner-only` item. The core MUST give the runtime adapter only the capability IDs, the access level, and whether the requester is the owner.
- **FR-014**: The system MUST find the target repo only through `runtime.claude.delegate_repos` of the receiving agent. Each path in the map MUST be inside one of the `repo_roots` entries of that agent.
- **FR-015**: The system MUST end a delegation with `status: failed` and a reason when it cannot make an MR. Reasons include `no changes`, `repo not available`, `unknown_target`, `target_required`, and `no merge request`.
- **FR-016**: The system MUST remove the worktree after a `write` step ends: after success, failure, and timeout.
- **FR-017**: The system MUST apply these rules from spec 003: the trust rules, the hop limit (3 or less), the claim rule, the step time limit with the "Retry" button, the owner-offline wait, and the catch-up.
- **FR-018**: The core MUST NOT name a worktree, git, a branch, an MR provider, or a runtime tool. Only the `claude` runtime adapter and the MR provider know them. The import-boundary test of spec 003 MUST cover the new core module.
- **FR-019**: A `write` plan step MAY have an optional field `target`, a string. The core MUST carry `target` as an opaque string in `RunRequest.target` and MUST NOT read its content. `validate_plan` MUST NOT check `target`, because the target agent keeps its map private. A repo path or a repo name MUST NOT enter the agent card (002 FR-017 stays unchanged).
- **FR-020**: The `claude` runtime adapter MUST resolve `target` with the owner map `runtime.claude.delegate_repos` (`{<name>: <absolute path>}`). (1) A `target` that is not in the map: the step fails with `status: failed` and `reason: unknown_target`. (2) The map has exactly one entry and the step has no `target`: the adapter uses that entry. (3) The map has more than one entry and the step has no `target`: the step fails with `reason: target_required`. (4) The map is empty: the step fails with `reason: repo not available` (the adapter refuses every `write` step). The planner does not see the repo names (accepted, DQ3): the request text must carry the name.
- **FR-021**: The system MUST NOT retry a rejected step. A rejected step MUST NOT have a "Retry" button (see FR-007). A pending gate button MUST NOT expire.
- **FR-022**: The system MUST start a delegation only from a plan step. A runtime result with `status: delegate` MUST NOT start a delegation. The core MUST ignore that status (the step fails as in spec 003).
- **FR-023**: For a `write` tag step (`agent: any`, spec 003), the gate MUST run for the agent that wins the claim. It MUST use the owner and the allowlist of that agent. An agent that lost the claim MUST NOT show a button. A `write` tag step MUST bind only to a capability whose card entry has no `access` or has `access: write` (decision LB1 of spec 003). The payload check (spec 003 FR-032) MUST run before the gate.
- **FR-024**: The `claude` adapter MUST build the deny list of a `write` run with `effective_deny_rules(deny_rules)` (spec 001): `Bash(git push:*)` is always in the list, plus the entries of `runtime.claude.deny_rules`. A config value `deny_rules: []` MUST NOT remove the push rule.
- **FR-025**: A `write` tag step that its winner rejected MUST end `failed`, `rejected`, and MUST get no second claimer. This MUST also hold after a restart of an adapter. The core uses `step_rejected` of spec 003 (FR-046). This spec adds no second rule.

### Key Entities

- **Delegation**: A `write` step for an agent of another owner. It has a sender, a receiver, a capability, a goal, and a result (an MR link).
- **Allowlist**: A list of `sender_id` values (bot ids and person ids) that the owner trusts to start `write` work without a button.
- **Gate decision**: The result of the owner gate for one step: `allow` (start) or `ask` (show the button).
- **Target**: An optional opaque name on a `write` step. The `claude` adapter maps it to a repo path through `runtime.claude.delegate_repos`. The name and the path never enter a card.
- **Worktree and branch**: An isolated copy of the repo for one run. It protects `main`.
- **MR**: The merge request. It is the result and the gate. The merge by a human is the approval.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tests, a `write` step from an allowlisted sender (with a trusted thread starter) starts without a button.
- **SC-002**: In 100% of tests, a `write` step that does not meet both conditions of FR-005 starts only after the owner accepts.
- **SC-003**: In 100% of tests, a reject gives `failed` with `reason: rejected`, no "Retry" button, and no work.
- **SC-004**: In 100% of tests, `main` has no change from an agent.
- **SC-005**: In 100% of successful delegations, the thread shows an MR link from a separate branch.
- **SC-006**: In 100% of tests, a `write` step cannot use an `owner-only` capability and cannot reach a file outside its worktree.
- **SC-007**: An owner can accept or reject a delegation in one click.
- **SC-008**: In 100% of builds, the import-boundary test passes with the new core module (no worktree, git, or MR-provider term in the core).
- **SC-009**: In 100% of tests, a click from a person who is not the owner changes nothing.
- **SC-010**: In 100% of tests, no worktree remains after a `write` step ends.
- **SC-011**: In 100% of tests, the four `target` cases give the result of FR-020: unknown, required, single-default, and empty map.
- **SC-012**: In 100% of tests, a `write` step from an allowlisted sender with a stranger as thread starter gets a button (DQ2).
- **SC-013**: In 100% of tests, a `write` tag step with two eligible agents gives one gate request at most: only the claim winner asks its owner. The loser shows no button.
- **SC-014**: In 100% of tests, the deny list of a `write` run holds `Bash(git push:*)`, also when the config has `deny_rules: []`.
- **SC-015**: In 100% of tests, a rejected `write` tag step gets no second claimer, also after a restart.

## Assumptions

- Specs 001, 002, and 003 exist (003 with its second batch: `core/source.py`, dialog, `exclude_agents_of`, `on_fail`, `step_rejected`).
- Each owner has the target repos checked out on the laptop under `repo_roots`. The owner names them in the config map `runtime.claude.delegate_repos` (DQ3).
- GitLab is the first MR provider. A human merges the MR.
- Only one owner's agent does the work in a step. A pipeline has at most 3 agent steps for a free plan and at most 5 for a verified template (spec 003 FR-042, constitution 1.3.0).
- The tool limits come from the access level and the run request, not from a step type.
- The review of the MR is part of spec 005. Trigger bots use the allowlist in spec 005.

## Notes for /speckit-plan

- Allowlist in `~/.pipe/config.yaml` (key `allowlist`): `sender_id` values (Slack: bot IDs and user IDs).
- Tag steps (spec 003, late binding): the gate runs for the agent that wins the claim, with its own owner and allowlist.
- Repo map in `~/.pipe/config.yaml` (key `runtime.claude.delegate_repos`). Only the `claude` adapter reads it.
- Pure gate function in the core. It reads no tool and no repo.
- Worktree, git, deny rules, and the MR provider only in the `claude` adapter and the provider.
- Never push to `main`. The adapter pushes only the branch of the step.
- Write the unit tests first (constitution principle VII).
