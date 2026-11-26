# Contract: Plan source and hop limit

Source: owner decision 5 for spec 006 (a security point), constitution 1.3.0. Spec FR-020 to FR-024. The functions `effective_source`, `hop_limit`, and `parse_source` and the constants are spec 003 code (`core/source.py`, [../../003-chat-pipelines/data-model.md](../../003-chat-pipelines/data-model.md)). This contract states the data rules that spec 006 gives them: the hash, the shape, and `Flow.matches(steps, cards, starter)`. The LLM never writes `pipeline.source`. Extends [../../003-chat-pipelines/contracts/plan-schema.md](../../003-chat-pipelines/contracts/plan-schema.md) and [../../003-chat-pipelines/contracts/task-metadata.md](../../003-chat-pipelines/contracts/task-metadata.md).

## Plan fields added

The `pipeline` object of the plan message (type 1) gets one field. Each plan step gets three optional fields.

| Field | Where | Rule |
|---|---|---|
| `source` | `pipeline` | `free` or `template:<name>@<hash>`. Missing means `free`. |
| `exclude_agents_of` | step | List of step indexes (integers) that are lower than the step index. |
| `gate` | step | `approval`. |
| `on_fail` | step | Index of a higher step. At most one step in a plan. The target is the last step. |

`<hash>` is 32 lower-case hex characters. `<name>` matches `^[a-z0-9-]{1,32}$`.

## The hash

`flow_hash(data)` = the first 32 hex characters of `sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True))`. `data` is the mapping that `yaml.safe_load` returns for a file that passed `validate_flow`. The hash does not depend on comments, white space, key order, or quote style. Any change of a step, a tag, a flag, a parameter, or the description changes the hash.

## Effective source

`effective_source(plan, flows, cards, starter) -> "template" | "free"` (spec 003) is a pure function. Condition 4 (the shape) is `Flow.matches(steps, cards, starter)` of spec 006. `flows` is the map of valid templates on this adapter (name to `Flow` with its `hash`). The result is `template` only when all these hold:

1. `plan.source` has the form `template:<name>@<hash>`.
2. `flows` has `<name>` (the override wins by name, as for the planner).
3. The `hash` of that template equals `<hash>`.
4. The plan steps match the template shape ("Shape" below).

Else the result is `free`. The function never raises. A bad `source` string gives `free`.

### Shape

The template, with the parameters that the plan shows, gives an expected list of steps. The plan matches when all hold:

- The step count is equal.
- For each step, `access`, `gate`, `on_fail`, and `exclude_agents_of` are equal.
- A tag step has `agent: any` and the expected tag. For `tag:$<param>` the tag is any value of that parameter.
- A `$agent` step has a bot agent with a trusted card. Its capability ID is in the card, has the expected tag, and has a fitting access.
- A human step has `agent` equal to `human:<starter>`.
- `goal`, `payload`, and `target` are not compared. They are free text or data of the person.

## Hop limit

Spec 003 defines `MAX_HOP_FREE = 3`, `MAX_HOP_TEMPLATE = 5`, and `hop_limit(effective) -> 5 if effective == "template" else 3`.

| Place | Rule |
|---|---|
| `validate_plan(plan, cards, starter, flows)` (planner) | The number of agent steps is at most `hop_limit(effective_source(...))`. Error: `plan has N agent steps, the limit is M`. |
| `route` (every receiver) | A handoff with `hop` greater than `hop_limit(effective_source(plan, ...))` gives `refuse`. |
| Refusal text | `hop limit exceeded`. When the declared source is a template and the effective source is `free`: `hop limit exceeded (plan source not verified)`. |

The branch handoff of `on_fail` adds 1 to `hop`. A dialog resume and a Retry add nothing.

## Who can claim a source, and how the core checks it

- Any agent with a trusted card can post a plan message. Only the plan message of the planner (the first named agent) counts (spec 003 `find_plan`). The `source` field is text. A modified planner, or a planner with a changed file, can write any value.
- The claim has no effect by itself. Every receiver recomputes the effective source with its own template files. The recompute needs the same hash and a matching shape.
- A forged claim fails in four ways: the name is unknown, the hash differs, the steps do not match, or the receiver has no copy. In all four cases the limit stays 3.
- A human edit of the steps makes the shape differ. The source becomes `free` with no extra rule. The planner also writes `free` in the new plan message.
- A planner with a changed local file (an override) gets a different hash. Receivers that have the git file see a hash mismatch. The override is personal. This is by design.
- The check does not stop a planner that has a bad file and a team that merged the bad file in git. The review of `flows/` in git is the control for that case. Each template is at most 5 agent steps. Every `write` step still meets the spec 004 gate and the human ✅.

## Failure cases

| Case | Effective source | Result |
|---|---|---|
| Receiver has no `flows/` directory | `free` | Refuses at `hop` 4 with the unverified text. |
| Receiver has an older copy of the file | `free` | Same. The person pulls the repository. |
| Plan has a template source and one more step | `free` | The planner rejects it at plan time when more than 3 steps. Receivers refuse at `hop` 4. |
| Plan source is `free` and has 4 agent steps | `free` | `validate_plan` error. |
| Edited plan | `free` | As above. |
