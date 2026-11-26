# Contract: Trigger mention, trigger card, and trigger gate

Source: design brief §3 decision 14, §6 (Triggers), §8. Spec FR-013 to FR-021, FR-023. Constitution 1.3.0. Extends [../../003-chat-pipelines/contracts/task-metadata.md](../../003-chat-pipelines/contracts/task-metadata.md) and [../../004-delegation/contracts/gate.md](../../004-delegation/contracts/gate.md). Fields are in [../data-model.md](../data-model.md).

## Trigger card (`pipe.card.v1`)

Posted and pinned once in `#pipe-agents` by the trigger bot (`post_trigger.py card`).

```json
{
  "name": "pipe-gitlab",
  "description": "GitLab CI trigger",
  "owner": "<slack_user_id>",
  "bot_id": "<bot_id>",
  "bot_user_id": "<slack_user_id of the bot>",
  "kind": "trigger",
  "mode": "ci",
  "skills": [],
  "hash": "<sha256 of the empty skills list>"
}
```

- `kind` is `trigger`. `skills` is empty. The card passes `validate_card` (no URL, token, or path).
- `bot_id` and `bot_user_id` come from `auth.test`.
- Only a card of `kind: trigger` can start a pipeline through a trigger mention.

## Trigger mention

A top-level message in `#pipe-work` (no `thread_ts`). It has one of two forms (DQ3). The two forms are exclusive.

- Form A, fixed pipeline. `text`: `<@AGENT_USER_ID> <title>`. The metadata holds a `pipeline`. The text has no `flow:` word.
- Form B, flow. `text`: `<@AGENT_USER_ID> flow:<name> <goal>`. The metadata has NO `pipeline`. The `goal` is not empty. The planner expands the template with the `plan_flow` action of spec 003 (no LLM call, no runtime call).
- The title or the goal is plain text. It is scrubbed and cut to 200 characters. The script escapes other mentions.
- A message with both forms, or with neither (a free goal text), has no effect (`bad_payload`). A free goal text never starts a pipeline.
- `metadata`: `{ "event_type": "pipe.task.v1", "event_payload": <payload> }`.

```json
{
  "v": 1,
  "phase": "plan",
  "status": "needs_approval",
  "by": "<bot_id of the trigger bot>",
  "hop": 0,
  "pipeline": { "steps": [ { "agent": "any", "capability": "tag:review", "access": "read", "goal": "Review the open MR", "payload": { "mr_url": "https://..." } } ] }
}
```

Rules:

1. `task_id` is absent. The `ts` of the message is the task ID.
2. `by` equals the `bot_id` of the Slack message. `hop` is 0. `next` is absent.
3. `pipeline` (form A) follows the 003 plan schema: steps with `agent`, `capability`, `access`, `goal`, and the optional `target`, `payload`, `exclude_agents_of`, `gate`, and `on_fail`. The trigger never writes `pipeline.source`: the receiver recomputes it with `effective_source`, and a fixed pipeline is `free` unless it matches a verified template. The mentioned agent checks the plan with `validate_plan(plan, cards, starter, flows)`. A review step in a fixed pipeline should carry `exclude_agents_of`.
4. The first mentioned agent is the planner. Another named agent ignores the message.
5. A message that fails any rule has no effect.
6. The `flow:` word is read by `flow_word` of spec 003. The route gives its result to `parse_trigger(msg, cards, flow)`.

## Gate

| Case | Result |
|---|---|
| Plan invalid, or unknown flow | Plan message `failed` (type 2), `reason` = errors or `could not build a plan (unknown flow)`. No button. |
| Trigger bot in the allowlist of the planner | Plan message, then the start handoff. No ✅. No button. |
| Trigger bot not in the allowlist | Plan message with the buttons Accept and Reject. No step starts. |

The buttons use the `action_id` values `pipe_accept` and `pipe_reject` of spec 004. They apply here to a type 1 plan message by the planner, in a thread whose parent is a trigger mention. These buttons are on type 1 (a plan). They are not the type 4 owner gate of spec 004 and not the type 5 gate of spec 003. A ✅ release of a type 5 gate in a trigger thread comes from the owner of the planner (spec 003).

| `action_id` | Effect | Who may click |
|---|---|---|
| `pipe_accept` | The planner posts the start handoff. The buttons are removed. | The card `owner` of the planner only. |
| `pipe_reject` | The plan message goes to `failed` with `reason: rejected`. The buttons are removed. | The card `owner` of the planner only. |

A click from any other person changes nothing and posts nothing. A second click changes nothing. A rejected plan has no "Retry" button. A pending button has no expiry. The buttons stay valid after an adapter restart.

## Texts (`render_task`)

```text
Trigger pipe-gitlab: needs approval. <@U_OWNER> Accept or reject this pipeline.
Trigger pipe-gitlab: failed. Reason: rejected
Plan rejected. step 2: agent B123 is a trigger bot
```

The goal is in the plan message. Every mention except the real owner mention is escaped. No text holds a token, a path, or a URL.

## Rules

1. A trigger bot only posts trigger mentions. It posts no handoff and no step message.
2. The plan check runs before the gate, so an invalid plan never shows a button.
3. After the start, every rule of spec 003 and spec 004 applies. The starter of the thread is the trigger bot. A `write` step uses the delegation gate of spec 004.
4. The trigger token lives only in the CI secret store (a masked variable). The script reads it from the environment and never prints it.
