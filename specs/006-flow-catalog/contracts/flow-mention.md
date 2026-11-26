# Contract: The `flow:` mention syntax

Source: owner decision 2 for spec 006. Spec FR-006 to FR-009. Extends [../../003-chat-pipelines/contracts/plan-schema.md](../../003-chat-pipelines/contracts/plan-schema.md).

## Syntax

Spec 003 `flow_word(text)` (in `core/route.py`) reads only the first word `flow:<name>`. The route uses it to decide `plan_flow`, and spec 005 uses it for a trigger. `parse_flow_mention` below is the full parse (parameters, goal, agent mentions). The planner calls it after the `plan_flow` decision. A trigger message (spec 005) has the text `flow:<name> <goal>` and no `pipeline`.

```text
@agent flow:<name> [key=value ...] <goal text>
@agent @other-agent flow:<name> <goal text>          # for a flow with $agent
```

Grammar (the pure function `parse_flow_mention(text, agent_users) -> FlowMention | None`):

- `name`: `^[a-z0-9-]{1,32}$`.
- The first word that starts a token and has the form `flow:<name>` counts. The word must be followed by a space or the end of the text. Later `flow:` words stay in the goal.
- Directly after the `flow:` word, each word of the form `key=value` is a parameter. `key` matches `^[a-z]{1,16}$` and `value` matches `^[a-z0-9-]{1,32}$`. The first word that is not a parameter ends the list.
- The goal is the rest of the text (the text before the `flow:` word and the text after the parameters), with all agent mentions removed, trimmed, and with white space made single.
- The agent mentions come from `agent_users` (spec 003 `mentions`). The first named agent with a trusted card is the planner. The next distinct named agents are `agents`.
- The result is `FlowMention(name, params, goal, agents)`. It is `None` when no `flow:` word exists.

The parser does not read markup (quotes, code blocks). Slack text is plain at this point (the `Transport` gives plain text).

## Rules

| Case | Result |
|---|---|
| `flow:` word and one agent | A pipeline request. The agent is the planner. (This relaxes FR-002 of spec 003.) |
| `flow:` word and two agents, the flow has `$agent` | The second agent fills `$agent`. |
| `flow:` word and two agents, the flow has no `$agent` | Error: `flow <name> takes no agent mention`. |
| The flow has `$agent` and one agent | Error: `flow <name> needs a second agent mention`. |
| Unknown name | Error: `flow <name> not found. Known flows: <list>`. |
| Unknown key | Error: `flow <name>: unknown parameter <key>`. |
| Empty goal | Allowed. `{goal}` becomes an empty string. |
| A `flow:` word in a thread reply | A reply is not a pipeline request (spec 003). It is `chat`. |

Every error becomes a rejected plan message (type 2, `failed`). It has no button.

## Free text (no `flow:` word)

The planner prompt gets the list of valid templates: `name` and `description` only. The plan schema has one more optional field:

```json
{ "flow": { "type": "string", "maxLength": 32 } }
```

When the output has `flow`, the planner ignores `steps`, loads the template of that name, and expands it with the thread goal. An unknown name is a planner error (`could not build a plan`). The LLM never writes steps for a template. The LLM may still return free `steps` with no `flow`. The source of that plan is `free`.

## Trigger text

A trigger mention (spec 005) can carry `flow:<name> [key=value ...] <goal>` as text and no `pipeline` (DQ8). The mentioned agent expands the template. The trigger rules of spec 005 (allowlist, button) apply to the expanded plan. A trigger message with both a `pipeline` and a `flow:` word is ignored (`bad_payload`).

## Gates and approval

The expansion result is a normal plan. It gets the status `needs_approval`. ✅ from the thread starter or the owner of the planner starts it (spec 003). A trigger thread follows spec 005. No part of the `flow:` syntax skips a gate.
