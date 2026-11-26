# Research: Review Capability and External Triggers

All items are resolved. One question (O1) is open in [plan.md](plan.md). The owner decisions DQ1 to DQ9 are in "Design decisions" of plan.md. Source: `docs/design-brief.md` §3 (decisions 8, 14, 15, 18), §6 (Triggers, Review), §9 (M4), constitution v1.3.0. No Slack access and no network call was used.

## Checked in the repository (2026-11-26)

- Specs 001 to 004 (pass 1 and pass 2) hold the model changes that 005 uses: late binding by tag (003 N-LB), config-declared capabilities (002), the `Transport` port and `upload_file` (001), `input_schema` and `check_input` (003), `effective_payload(step_payload, results)` (003 FR-037), `exclude_agents_of` (003 FR-039), `on_fail` (003 FR-040), and `plan_flow` (003 FR-044). They do NOT hold the claimant rule (`duplicate_handoff`, `not_claimant`): 005 T005 and T006 add it.
- 003 already says: "A review step is a normal `read` step whose capability has the tag `review`. The core has no review code."
- 003 `route` rule 2 ignores a bot message when `next.agent` is not this adapter. A top-level trigger mention has no `next`. So 005 needs a new route rule.
- 003 `find_plan` takes the earliest plan message whose `by` is the planner. A trigger mention is by the trigger bot. So it never counts as the plan.
- 003 ✅ counts from the thread starter or the planner owner. For a trigger thread the starter is a bot, so only the owner counts.
- 004 `in_allowlist` is an exact match on a Slack ID. It fits a trigger bot ID. 004 says that spec 005 uses it.
- 004 buttons `pipe_accept` and `pipe_reject` exist for a type 4 message. 005 reuses the same IDs and the same click rule on a type 1 message.
- 002 card: `kind` is `agent` now. The `trigger` kind is for spec 005.

## Decisions

### D1. A review step needs no core code
- Decision: the plan check, the claim, the run, the timeout, and the "Retry" button of 003 handle a review step. The only review term is the tag `review`. It is data in the plan (`tag:review`) and in the config `tags` map.
- Rationale: principle XI and brief decision 8.
- Alternatives: a `review` step type or a callback in the core. Rejected by the brief.

### D2. Slow completion is the end of a capability run
- Decision: the claiming adapter calls the capability adapter. The call returns when the work ends. The adapter then posts `done` or `failed`. The core knows no "slow" flag. The step time limit stops a call that does not end.
- Rationale: no new message type, no new status, and no new trust path (FR-008). 003 already has the claim, `running`, `failed`, and "Retry".
- Alternatives: a callback to the adapter (new local trust path), or a separate bot (second runtime). See DQ1.

### D3. A completion counts only from the claimant
- Decision: a `done` or a handoff counts only when its `by` is the bot that holds the winning claim for that step. The earliest trusted handoff for a step wins. A later handoff is ignored (`duplicate_handoff`).
- Rationale: FR-006 and FR-008. With `agent: any`, no plan field names the agent, so the claim is the only proof. This is a pure rule in `route` and `pipeline.py`.
- Alternatives: dedupe by message `ts` only. It does not stop a second agent from advancing the pipeline.

### D4. Payload and the change link
- Decision: spec 003 `effective_payload(step_payload, results) -> dict` (FR-037, D27). It adds `context` (a list of `{step, text, artifacts}` of ALL earlier done steps) and `artifacts` (all links). A plan key wins. The core treats all values as opaque. 005 defines no payload function. See DQ2.
- Rationale: the MR link exists only after an earlier step ends. The core stays generic.

### D5. Input check for the review capability
- Decision: the review capability declares an `input_schema` that needs a change link (a string `mr_url` or a non-empty `artifacts` list). The check of 003 (`check_input`) runs on the effective payload before the run. A schema with `additionalProperties: false` must list `context` and `artifacts`. A failure gives `failed` and `reason: invalid_payload`.
- Rationale: FR-011. No external request is sent for a bad payload.

### D6. The wiz-review wrapper
- Decision: `templates/review/wiz_review_capability.py` reads the payload (JSON on stdin) and finds the change link. It asks the wiz-review state. It sends one request when no review exists. It polls until the drafts are ready or an error shows. Then it prints one JSON result (`text`, optional `status`, `artifacts`, `data`, `files`). Exit code 0 is success. A wrapper for e2e or a long test uses the same output: `{status: failed}` with exit 0 takes `on_fail`, and a non-zero exit gives `RuntimeFailed` with no branch (003 FR-040). Another exit code is a failure, and the stderr text (scrubbed) is the reason. The wiz-review commands come from environment variables of the declared capability, so the wrapper has no hard-coded command path.
- Rationale: DQ1 = (a). The wrapper is idempotent: it asks the state first, so a "Retry" sends no second request (FR-012). It has no loop limit. The adapter step timeout ends it (DQ6).
- Ceiling: a poll costs one local command every 15 seconds. The wrapper holds one child process for the length of the review.
- Cannot verify: the real wiz-review request and state commands (assumption A1). Task T031 checks them.

### D7. Trigger message shape
- Decision: see [contracts/trigger-message.md](contracts/trigger-message.md). A top-level message in `#pipe-work`. Text starts with `<@agent_user_id>`. Metadata `pipe.task.v1` with `v`, `phase: plan`, `status: needs_approval`, `by`, `hop: 0`, and EITHER `pipeline` (form A) OR no `pipeline` with `flow:<name> <goal>` in the text (form B, DQ3). Both or neither: `bad_payload`. It has no `task_id`, because the `ts` is unknown before the post. `parse_trigger` reads the message with its own small parser.
- Rationale: DQ3 = (a). The planner (first mention) turns it into a normal plan message and a start handoff, so all later code is the 003 code.

### D8. Trigger gate
- Decision: `decide_trigger(sender, allowlist) -> Gate`. `allow` when `in_allowlist(allowlist, sender)`. Else `ask`. It reuses the `Gate` dataclass of 004, with reasons `allowlisted` and `not_allowlisted`.
- Rationale: FR-015 and brief decision 14. One generic allowlist serves both specs.

### D9. Trigger flow in the adapter
- Decision: the planner adapter does these steps in order: (1) `route` gives `trigger`. (2) for form B: the `plan_flow` expansion (003, no runtime call); then `validate_plan(plan, cards, starter=<trigger bot>, flows)`. Errors give a rejected plan message (type 2), with no button. (3) The adapter posts a plan message (type 1, `needs_approval`) with the same pipeline. (4) `allow`: the adapter posts the start handoff (type 3) at once. `ask`: the adapter adds the buttons to the plan message. (5) Accept gives the start handoff. Reject updates the plan message to `failed` with `reason: rejected`.
- Rationale: it reuses type 1, type 2, type 3, `start`, and the 004 click rule. No new message type.
- Ceiling: two posts for an allowlisted trigger (plan, then start).

### D10. A trigger bot is not a step agent
- Decision: `validate_plan` reports an error for a step whose agent has a card of `kind: trigger`. `route` ignores a bot message with `next` from a trigger bot (`trigger_not_agent`). The card has no skills, so a capability step cannot name it anyway. The check makes the rule explicit (FR-017).

### D11. Catch-up
- Decision: `Wake` also gives `trigger` for a parent message. The parent must meet three conditions. It is by a trigger bot with a valid trigger payload. It names this adapter as the first mention. It has no plan message by this adapter. The 001 catch-up already reads history after the last seen `ts`.
- Rationale: a nightly schedule runs when the laptop is off. The edge case in the spec needs it.

### D12. Trigger template
- Decision: `post_trigger.py` has two commands. `card` posts and pins the card (`kind: trigger`, empty `skills`, `hash` of the empty list). `post` builds and posts one trigger mention. Settings come from environment variables: the token variable, the channel, the agent user ID, and the pipeline file path. The script never prints the token. The CI job file (`gitlab-ci.yml`) lists the variable names only.
- Rationale: FR-020 and FR-023. The script is CI-agnostic. Only the job file is GitLab-specific. A unit test checks that the card passes the core `validate_card`.
- Slack scopes of the `pipe-gitlab` app: `chat:write` and `pins:write`. It needs no event scope.

### D13. Metrics
- Decision: no change. `compute_metrics` (003) reads the thread messages. A trigger pipeline is a normal pipeline. A trigger thread has a bot as starter. The "chat pipelines" metric counts it when it has no human message after the start (003 Q8). The owner can read the starter ID to split trigger pipelines later.

### D14. Files of a wrapper (open question O1)
- Decision: the optional output field `files` of the `exec` adapter. The stepper (outside the core) calls `Transport.upload_file` for each path and appends the links to `artifacts`. `UploadRefused` gives `reason: upload refused`. The core never reads a file.
- Rationale: spec 001 FR-024 says the caller puts the link in `artifacts`, and no spec names the caller. The wrapper holds no Slack token, so it cannot upload. See plan.md O1.

### D15. Plan source of a trigger plan
- Decision: a fixed `pipeline` from a trigger is checked like any plan. `pipeline.source` is recomputed (`effective_source`, 003 N7). A fixed pipeline is `free` unless it matches a verified template, so the `hop` limit is 3 unless the receiver verifies a template. A `flow:` trigger expands a template, so its source is the template source and the limit is 5.

## Cannot verify without real systems (assumptions)

- A1: the wiz-review request and state commands and their output. Task T031.
- A2: Slack sends an `app_mention` or a message event for a bot-posted mention of another app. 003 handoffs already rely on this. Task T032 checks it with the trigger bot.
- A3: the pinned card of a bot with no adapter passes the 003 `trusted_cards` check (message `user` equals `bot_user_id`). Task T032.
- A4: a GitLab schedule job can reach `slack.com` and read a masked variable. Task T033.
