# Data Model: Review Capability and External Triggers

All core entities are frozen dataclasses in `src/pipe/core/`. Nothing is stored in a file. The state lives in the thread messages (`pipe.task.v1`). This file adds to [../003-chat-pipelines/data-model.md](../003-chat-pipelines/data-model.md) and [../004-delegation/data-model.md](../004-delegation/data-model.md). It does not repeat them.

## Config keys

005 adds no config key to the core. It uses these existing keys:

| Key | Defined by | Use in 005 |
|---|---|---|
| `allowlist` | 004 | A trigger bot ID is an entry. `^[BUW][A-Z0-9]{2,}$`. |
| `tags` | 001/002 brief §5.4 | The owner maps the wiz-review capability ID to `[review]`. |
| `exposed` | 001/002 | The owner exposes the review capability. |
| `step_timeout_min` | 001 | Limit for a slow capability (DQ6). |
| declared capabilities | 002 (model update) | The wiz-review wrapper is one declared capability. |

Environment variables of the trigger template (CI side, not the config file): `PIPE_TRIGGER_TOKEN` (masked), `PIPE_CHANNEL`, `PIPE_AGENT_USER_ID`, `PIPE_PIPELINE_FILE` (form A), `PIPE_FLOW` (form B, a flow name), `PIPE_TRIGGER_TITLE` (the title, or the goal for form B). Form A and form B are exclusive. The token variable holds a value only in the CI settings. No file holds it.

## Trigger (core)
File: `src/pipe/core/trigger.py`. Pure. Names no CI tool.

```python
@dataclass(frozen=True)
class Trigger:
    ts: str                  # Slack ts of the trigger message (it becomes the task id)
    sender: str              # bot_id of the trigger bot
    pipeline: Pipeline | None  # form A: steps, as in 003 (the source is recomputed, never trusted)
    flow: str | None         # form B: the flow name from flow_word (spec 003)
    title: str               # scrubbed text after the mention (form B: the goal, not empty), at most 200 characters

def parse_trigger(msg, cards, flow: str | None) -> Trigger | None: ...   # flow = flow_word(msg.text), computed by the route
def decide_trigger(sender, allowlist) -> Gate: ...     # Gate from 004: action allow|ask, reason allowlisted|not_allowlisted
```

`parse_trigger` returns a `Trigger` only when all hold:

1. The message is top-level (`thread_ts` is absent or equal to `ts`).
2. `cards[bot_id]` exists, passes the 003 trust check, and has `kind: trigger`.
3. The payload has `v: 1`, `phase: plan`, `status: needs_approval`, `hop: 0`, and `by` equal to the message `bot_id`. It has no `next`.
4. Exactly one of two forms: the payload has a `pipeline` that parses as a 003 `Pipeline` shape and `flow` is `None` (form A), or the payload has no `pipeline`, `flow` is a name, and the title is not empty (form B). Both, or neither, give `None`. (The plan rules of `validate_plan` are not checked here.)

Otherwise it returns `None`. The route gives the reason (`no_card`, `not_trigger`, `bad_payload`, `trigger_not_agent`).

`decide_trigger` is `Gate("allow", "allowlisted")` when `in_allowlist(allowlist, sender)`, else `Gate("ask", "not_allowlisted")`. A `None` or empty sender gives `ask`.

## Trigger mention (Slack message)
See [contracts/trigger-message.md](contracts/trigger-message.md). Fields: `text`, `metadata.event_type = pipe.task.v1`, `metadata.event_payload` (`v`, `phase`, `status`, `by`, `hop`, and `pipeline` for form A only). No `task_id`, no `source`.

## Trigger card
Shape: 002 card. `kind: trigger`. `skills: []`. `hash`: sha256 of the canonical JSON of the empty list. `mode: ci`. `owner`: the Slack user ID of the person who owns the trigger bot. It holds no URL, token, or path.

## Step and plan changes

| Rule | Where | Text |
|---|---|---|
| Trigger agent | `validate_plan` | An error `step N: agent B1 is a trigger bot` when `cards[agent].kind == trigger`. |
| Claimant | `route`, `step_status` | A handoff or `done` for step `i` counts only when `by` is the bot of the winning claim of the step before (or of step `i`). |
| First handoff | `route` | For step `i`, only the earliest trusted handoff gives `claim`. A later one gives `ignore(duplicate_handoff)`. |

## Effective payload
File: `src/pipe/core/runrequest.py`.

Spec 003 owns `effective_payload(step_payload, results)` (`core/runrequest.py`, FR-037). 005 does not change it. `results` is the list of `{step, text, artifacts}` of the done steps before the step. The result is the plan `payload` plus `context` and `artifacts` (all links). A key that the plan sets wins. `check_input` validates this effective payload.

## Route changes
New `Decision` actions: `trigger` (arg: the `Trigger`) and `reject_plan` (arg: the plan message). The action `start` also comes from a click on Accept. For form B, the `trigger` action runs the 003 `plan_flow` expansion in the planner. The 003 actions `plan_flow`, `release`, `resume`, and `expire_dialog` are not changed.

| Event | Rule |
|---|---|
| top-level `BotMessage` from a card of `kind: trigger` | If this adapter is the first mentioned agent and `parse_trigger` works: `trigger`. Another mentioned agent: `ignore(not_planner)`. Payload fails (also both forms or neither form): `ignore(bad_payload)`. |
| top-level `BotMessage` from a card of `kind: agent` or no card | `ignore(not_trigger)` or `ignore(no_card)`. |
| `BotMessage` with `next` from a trigger bot | `ignore(trigger_not_agent)`. |
| `Click` `accept` on a type 1 message by this adapter, status `needs_approval`, parent by a trigger bot, clicker is the card `owner` | `start`. |
| `Click` `reject` on the same message | `reject_plan`. |
| `Click` on a message with `reason: rejected` | `ignore` (no Retry). |
| `Wake` | `trigger` for each open trigger parent with no plan message by this adapter. |

## States of a trigger thread

```text
trigger mention (by trigger bot)
  plan invalid or unknown flow -> type 2 plan message, status failed, reason = errors (end)
  plan valid, allow   -> type 1 plan (needs_approval) -> type 3 start (done)      -> normal pipeline
  plan valid, ask     -> type 1 plan (needs_approval + Accept/Reject)
                           Accept -> type 3 start                                  -> normal pipeline
                           Reject -> type 1 plan, status failed, reason rejected   (end)
```

`thread_status` (003) needs no change: a plan message with `failed` gives `rejected`.
