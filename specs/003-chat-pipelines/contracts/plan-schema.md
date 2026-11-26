# Contract: Planner call and plan check

Source: design brief §6 ("Pipeline from chat"). Spec FR-002 to FR-005, FR-039 to FR-044.

## Who plans

The planner is the first agent that the parent message names. The pure function `first_agent(text, agent_users)` reads the `<@U...>` mentions in text order and returns the first one that maps to a trusted card. The adapter of that agent runs the planner. The other named adapters ignore the message.

## Planner call (`planner.run_planner`)

- Runtime: `RuntimePort` (001) with `schema=PLAN_SCHEMA` and `request = RunRequest((), "read", False)` (no capability, not owner). The planner always uses this request, also for the owner (confirmed decision). The planner code knows no flag. The `claude` adapter maps the request to the 001 flags with `--json-schema` set to the plan schema and `--tools ""`. It adds no `--allowedTools`, no `--add-dir`, and no load set. `--restricted` stays.
- `RuntimeInput.task`: `{id: thread_ts, purpose: "plan"}`. `purpose` is the label of the call (001).
- Prompt (in this order): (1) a fixed instruction: build a plan from the cards; use only the listed agents and capability IDs; every bot step has a `capability` and `access` `read`; a step may use `agent` `any` with `capability` `tag:<tag>` when the request does not name one agent and a card offers the tag; a step may have a `payload` object only when the card entry of the capability has an `input_schema`, and then it must match that schema; a human step has `access` `approve`, no capability, and is the last step; at most 3 bot steps; a step that reviews or checks earlier work has `exclude_agents_of` with the indexes of the earlier steps that it checks; a step may have `gate: approval` or (at most once, only on a step before the last, and only when the last step is a bot step) `on_fail` with the index of the last step; (when the template list is given) the output may be only `{"flow": "<name>"}` when one listed template fits the request; (2) the card list as data: for each agent `name`, `bot_id`, and for each capability (card `skills[]`) the `id`, the `tags`, the `access` (when present), the `input_schema` (when present), and the sanitized `description`; (3) the thread, in a block labeled untrusted data (001 D7).
- The card list holds no `owner`, no URL, no path. When the adapter has templates (`ThreadState.flows`), the prompt also lists each template as `name` and `description` only (data, spec 006).

## Plan schema (`--json-schema`)

```json
{
  "type": "object",
  "anyOf": [ { "required": ["steps"] }, { "required": ["flow"] } ],
  "properties": {
    "steps": {
      "type": "array",
      "minItems": 1,
      "maxItems": 4,
      "items": {
        "type": "object",
        "required": ["agent", "access", "goal"],
        "properties": {
          "agent": { "type": "string" },
          "access": { "enum": ["read", "write", "approve"] },
          "goal": { "type": "string", "maxLength": 500 },
          "capability": { "type": "string" },
          "payload": { "type": "object" },
          "target": { "type": "string", "maxLength": 64 },
          "exclude_agents_of": { "type": "array", "items": { "type": "integer", "minimum": 0 }, "maxItems": 5 },
          "gate": { "enum": ["approval"] },
          "on_fail": { "type": "integer", "minimum": 1 }
        }
      }
    },
    "flow": { "type": "string", "maxLength": 32 }
  }
}
```

The schema has NO `source` field. The planner core sets `pipeline.source` (FR-042): `free` for a plan from `steps`, and `template:<name>@<hash>` only for the expansion of a template by the core. `maxItems` stays 4 (3 bot steps and 1 human step): the LLM writes free plans only, and a template path has no LLM steps. When the output has `flow`, the planner ignores `steps`, expands the template of that name (spec 006 `expand_flow`) and runs `validate_plan` on the result. An unknown name gives `could not build a plan (unknown flow)`. The optional `target` is an extension of spec 004 (an opaque repo name for a `write` step). Spec 004 owns it. The core carries it and never reads it. `validate_plan` does not check it. The enum has `write` because spec 004 defines `write` steps. In 003 alone, `validate_plan` still rejects `write`. After 004, `validate_plan` accepts `write` for a bot step. The planner prompt rule "use `write` only when the goal changes files" is added by spec 004. The schema limits the shape only. `validate_plan` checks the rules in code (data-model.md "Pipeline (plan)"). The LLM output is never trusted.

## Plan from a `flow:` word (no LLM)

When the `route` decision is `plan_flow` (FR-044), the planner does not call the runtime. It reads `flow:<name>` and the parameters, expands the template with `expand_flow` of spec 006 (a pure function), sets `pipeline.source`, and runs `validate_plan(plan, cards, starter, flows)`. An error gives a type 2 message. A valid plan gives a type 1 message with the status `needs_approval`.

## After the call

1. Parse the output. A runtime failure, a timeout, or bad JSON gives a type 2 message with `reason: could not build a plan (<short reason>)`.
2. Call `validate_plan(plan, cards, starter, flows)`. Errors give a type 2 message with the errors in `reason` and in the text (FR-004). No ✅ can start this plan.
3. A valid plan gives a type 1 message (FR-005). The text lists the steps with the agent names.

## Run of a step (`read` access)

- `RuntimeInput.task`: `{id: thread_ts, purpose: "step", step: <index>, payload: <payload, when the step has one>, pipeline: {"goal": <goal>}}`. `purpose` is the label of the call (001). No `hop`, `from_agent`, `owner`, or trust data.
- Before the run (after the claim, before any gate): for a tag step, `bind_step` sets the capability of this agent. `check_input(step, cap)` validates the `payload` (FR-032). A failure ends the step with `reason: invalid_payload`.
- `RuntimeInput.request`: `build_run_request(step, starter, owner, output_schema)` (research.md D9, [runtime-request.md](runtime-request.md)). The runtime adapter is picked by `pick_runtime`.
- The `payload` of the run input is `effective_payload(step.payload, results of earlier done steps)` (FR-037). `check_input` validates it.
- After the run: `check_output(output, cap)` validates `data` (FR-033). A failure ends the step with `reason: invalid_result`.
- Result handling (see [runtime-request.md](runtime-request.md) "Runtime output"): `waiting` with `needs_input` starts the dialog (type 10). `done` with a `proposal` is gated (type 5 `needs_approval`). `failed` gives `run_failed` and the branch rule.
- Load and flags: only the `claude` adapter. It maps the request, calls `prepare` (002), builds the command, and calls `cleanup` after the run. The stepper does none of this.
- The prompt has the thread (untrusted) and the line `Step goal: <goal>`.
