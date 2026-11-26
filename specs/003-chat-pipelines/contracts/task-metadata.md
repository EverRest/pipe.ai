# Contract: Task messages (`pipe.task.v1`)

Source: design brief §5.2, §6, §7. Spec FR-012, FR-020, FR-036 to FR-046. All messages are in the thread of one task in `#pipe-work`. The `thread_ts` of the parent message is the `task_id`. Fields are in [../data-model.md](../data-model.md) (TaskMsg).

## Message (Transport)

- `metadata`: `{ "event_type": "pipe.task.v1", "event_payload": <TaskMsg> }`.
- `text`: made by `render_task` (see "Texts"). It passes `scrub` and `escape_mentions` (both from the `Formatter` of the `Transport`). Only the mention of the next agent is added after the escape step. The mention is `Transport.mention(bot_user_id)` (Slack: `<@bot_user_id>`) with `bot_user_id` from the card of that agent (no transport lookup).
- Update: `Transport.update_message` of the same `ts` with the new `text`, the new `metadata`, and the new `buttons` (Slack: `chat.update` needs all three).
- Read: `conversations.replies` with `include_all_metadata`.

## Message types

| # | Type | Posted by | `phase` / `access` | `status` | Other fields | Update |
|---|---|---|---|---|---|---|
| 1 | Plan | planner | `plan` / none | `needs_approval` | `pipeline`, `step: 0`, `hop: 0` | Never. |
| 2 | Rejected plan | planner | `plan` / none | `failed` | `reason` (the errors), `hop: 0` | Never. |
| 3 | Start handoff | planner, after ✅ | `plan` / none | `done` | `hop: 1`, `step: 0`, `next: {agent, access, payload: {step: 0}}` | Never. |
| 4 | Step claim | the assigned agent, at receipt | `step` / the step `access` | `claimed`, then `running`, then `done`, `failed`, or `waiting`. For a `write` step (spec 004): `claimed`, then `needs_approval` (owner gate), then `running` or `failed` with `reason: rejected` | `step`, `hop` (the `hop` of the handoff), `reason` on `failed` | In place. Deleted if the claim loses. |
| 5 | Step result | the assigned agent, at the end of the step | `step` / the step `access` | `done`; or `needs_approval` when the step has `gate: approval` or returns a `proposal` (FR-043, FR-038) | `step`, `hop + 1` when `next` is set (else the `hop` of the claim), `next` (if the next step is a bot step; none in the `needs_approval` form), `artifacts`, `pipeline` (the proposal, only in the `needs_approval` form) | Never. A ✅ release (FR-043) makes the same adapter post a NEW type 5 `done` (or type 6, or the final type 5). The `needs_approval` message stays. The newer message is the status of the step. |
| 6 | Approval request | the agent of the last bot step | `step` / `approve` | `needs_approval`, then `done` | `step` (index of the human step), `hop` (same as the claim), button | In place: button click sets `done`. |
| 7 | Waiting | the sender of a handoff | `step` / the access of the waiting step | `waiting` | `step`, `reason: owner offline` | Never. |
| 8 | Hop refusal | the adapter that refuses | `step` / the `next.access` | `failed` | `step`, `hop` (as received), `reason: hop limit exceeded` | Never. |
| 9 | No claimer | the sender of the handoff of a tag step | `step` / the step access | `failed` | `step`, `hop` (as in the handoff), `reason: no_claimer`, button | Never. |
| 10 | Dialog question | the claiming agent, when the runtime returns `waiting` with `needs_input` | `step` / the step access | `waiting`; then `running` (after a valid answer, in place) or `failed` with `reason: dialog_timeout` and a "Retry" button (in place) | `step`, `hop` (the `hop` of the claim), `reason: needs_input`. The text is the question. It mentions the thread starter and tells the person to mention the agent in the answer. | In place. |
| 11 | Branch handoff | the claiming agent of a step that has `on_fail`, when the runtime returns `status: failed` (`run_failed`) | `step` / the `next.access` | `failed` | `step` (the failed step), `hop + 1`, `reason: run_failed`, `next: {agent, access, payload: {step: <on_fail index>}}`. No button. | Never. |

The field named `kind` is not used in a task message. A step ends when its agent posts `status: done` in the thread (type 5, or type 4 set to `done` and then type 5). The core does this for every capability, including a review capability.

Rules:

1a. A tag step (plan `agent: any`) has a start or result message (type 3 or 5) with `next.agent: any`. The text mentions every eligible agent. The first claim with the lowest `ts` wins. The messages of the step after the claim come from the winner only. If no valid claim exists after `step_timeout_min`, the sender posts type 9 (`no_claimer`) with a "Retry" button. A click posts the handoff again with the same `hop`.
1. A step with status `failed` has a "Retry" button (type 4, type 9, or type 10), with two exceptions: a step with `reason: rejected` (spec 004) has no "Retry" button (the requester starts a new thread), and a step that has a type 11 message has none (rule 8). Type 8 and type 11 have no button.
2. The last bot step posts type 5 without `next` when there is no human step after it. Then the thread is `done` (`thread_status`).
3. If the last step is a human step, the agent of the step before it posts type 6 instead of type 5. The claim message of that step goes to `done`. The reply text of the step is in type 6.
4. `hop` rule: see research.md D6. A receiver refuses a handoff with `hop` greater than `hop_limit(effective_source)`: 3 for a free plan, 5 for a verified template (FR-042). The text is `hop limit exceeded`, with the suffix ` (plan source not verified)` when a declared template is not verified.
5. The goal and the capability of a step come from the plan (type 1), not from `next.payload`.
6. Only a message that passes `check_task_msg` has an effect (research.md D4).
7. Trust checks of the new types (all inside `check_task_msg`, all use `step_agent`):
   - Type 10: `by` equals `step_agent(thread, step)`. `status` is `waiting`, `running`, or `failed`. `reason` is `needs_input` (or `dialog_timeout` when `failed`). `hop` equals the `hop` of the claim. Else the message is ignored (`not_assigned`, `bad_payload`).
   - Type 11: `by` equals `step_agent(thread, step)`. The plan step has `on_fail` equal to `next.payload.step`. `reason` is `run_failed`. `status` is `failed`. The thread has no other type 11 message (else `already_branched`). Else it is ignored (`bad_branch`).
   - Type 5 with `needs_approval`: `by` equals `step_agent(thread, step)`. A `pipeline` counts as a proposal only when `validate_plan` (free, no flows) returns no error. Else the receiver treats the message as a gate with no proposal and logs `bad_proposal`.
   - A dialog answer is a human message, not a task message. It counts only from the thread starter or the card owner of the agent that asked, and it must mention that agent. Another sender gives `chat` (001).
8. A failed message that carries `next` (type 11) has no "Retry" button. A "Retry" click on a failed message of a step that has a type 11 message gives `ignore(already_branched)`.
9. Only these `failed` reasons take the branch: `run_failed`. Every other reason uses "Retry" (FR-040).
10. A gate release posts once. The in-flight key is `release:<channel>:<ts>`. A second ✅ gives `ignore` because a `done` message of the step exists.

## Buttons

The core builds a list of `Button(action_id, label)`. The `Transport` shows them (Slack: a Block Kit `actions` block) and sends a click as a `ClickEvent` to the app that posted the message (Slack: `block_actions`).

| `action_id` | On message | Label | Effect | Who may click |
|---|---|---|---|---|
| `pipe_approve` | type 6 | Approve | The message goes to `done`. The thread is `done`. | The thread starter or the owner of the agent that posted the button. |
| `pipe_retry` | type 4, type 9, or type 10 with `failed` (not with `reason: rejected`, spec 004; not on a step that has a type 11 message) | Retry | Type 4 and type 10: a new claim for the same step. Type 9: the handoff is posted again. The button is removed. | The thread starter or the owner of the agent that posted the button. |

Spec 004 adds the buttons `pipe_accept` and `pipe_reject` on a type 4 message with `status: needs_approval` ([../../004-delegation/contracts/gate.md](../../004-delegation/contracts/gate.md)). Spec 005 also uses `pipe_accept` and `pipe_reject` on a type 1 plan message in a thread whose parent is a trigger mention ([../../005-review-gitlab-triggers/contracts/trigger-message.md](../../005-review-gitlab-triggers/contracts/trigger-message.md)). Only the card owner of the planner may click. A click from another person changes nothing and posts nothing. The adapter logs it.

## Reactions

- ✅ is the reaction `white_check_mark`. It counts only (a) on a type 1 message that has `status: needs_approval` (`start`), and (b) on a type 5 message that has `status: needs_approval` and a pending gate (`release`), from the thread starter or the owner of the planner. A ✅ on the plan does not release a gate. The `release` of a trigger thread follows the same rule: the starter is the trigger bot, so the owner of the planner (the mentioned agent) releases it (spec 005).
- 🔇 is the reaction `mute`. It marks a noisy agent message. Only `pipe metrics` reads it.

## Texts (`render_task`)

Short lines. Names come from the cards. Examples:

```text
Plan (needs approval). React with :white_check_mark: to start.
1. coder-pavlo (read): add endpoint X
2. reviewer-olena (read): review the change
3. human U123 (approve): confirm the result

Plan rejected. step 2: agent B123 has no card

Step 1 of 3 (read, coder-pavlo): claimed
Step 1 of 3 (read, coder-pavlo): running
Step 1 of 3 (read, coder-pavlo): failed. Reason: timeout
Step 2 of 3 (read, reviewer-olena): waiting. Reason: owner offline
Step 2 of 3 (read, any agent with tag review): failed. Reason: no_claimer
Step 2 of 3 (read, coder-pavlo): failed. Reason: invalid_payload
Step 1 of 4 (read, coder-pavlo): waiting for input. <question> Answer in this thread and mention <@U_AGENT>.
Step 1 of 4 (read, coder-pavlo): failed. Reason: dialog_timeout
Step 1 of 4 (read, coder-pavlo): needs approval. React with :white_check_mark: to go on.
Step 1 of 2 (read, any agent with tag e2e): failed. Reason: run_failed. <@U_NEXT> Branch: step 2 of 2 (read): troubleshoot
<reply text of the step>
<@U_NEXT> Step 2 of 3 (read): review the change
<@U123> Approve step 3 of 3: confirm the result
Stopped. Reason: hop limit exceeded
Stopped. Reason: hop limit exceeded (plan source not verified)
```

No text holds a token-like string, a path, or an MCP URL.
