# Data Model: Flow Catalog

All core entities are frozen dataclasses in `src/pipe/core/flows.py`. The core does no file I/O. A loader outside the core (`src/pipe/flows_io.py`) reads the files and gives the core plain data. Nothing is stored. The state is in the thread messages (`pipe.task.v1`). This file adds to [../003-chat-pipelines/data-model.md](../003-chat-pipelines/data-model.md), [../004-delegation/data-model.md](../004-delegation/data-model.md), and [../005-review-gitlab-triggers/data-model.md](../005-review-gitlab-triggers/data-model.md). It does not repeat them.

## Config keys

| Key | Type | Rule |
|---|---|---|
| `flows_dir` | str? | Optional. Path of the shared template directory. Default: `flows/` in the checkout that runs `pipe`. Read by `flows_io.py` only. |
| `dialog_timeout_h` | int | Spec 003 key (default 24, 1 to 168). The time that a step waits for a human reply (`needs_input`). After it: `failed`, `dialog_timeout`. 006 only uses it. |
| `tags` | map | Existing (spec 002). The owner maps capability IDs to tags. |
| `step_timeout_min` | int | Existing (spec 001). |

The override directory is the fixed path `~/.pipe/flows/`. It is not a config key. 006 adds no other key and no secret.

Constants in code: `MAX_TEMPLATE_BYTES = 20000`, `MAX_TEMPLATE_GOAL = 300`, `MAX_TEMPLATE_STEPS = 6` (5 agent steps and 1 human step). `MAX_HOP_FREE` and `MAX_HOP_TEMPLATE` are in spec 003 `core/source.py`.

## TagInfo and vocabulary

```python
@dataclass(frozen=True)
class TagInfo:
    name: str          # ^[a-z0-9-]{1,32}$
    access: str        # "read" | "write"
    meaning: str       # 1 to 120 characters

Vocabulary = Mapping[str, TagInfo]
```

`validate_tags(data) -> list[str]` and `parse_tags(data) -> Vocabulary` are pure. The loader reads `flows/tags.yaml` and calls them. Rules: [contracts/tag-vocabulary.md](contracts/tag-vocabulary.md).

## Flow and FlowStep

```python
@dataclass(frozen=True)
class FlowStep:
    id: str
    agent: str                       # "any" | "$agent" | "$starter"
    capability: str | None           # "tag:<tag>" | "tag:$<param>"; None for the human step
    access: str                      # read | write | approve (defaults applied)
    goal: str
    payload: Mapping | None
    gate: str | None                 # "approval" | None
    exclude_agents_of: tuple[str, ...]   # step ids
    on_fail: str | None              # step id

@dataclass(frozen=True)
class FlowParam:
    values: tuple[str, ...]
    default: str

@dataclass(frozen=True)
class Flow:
    name: str
    description: str
    params: Mapping[str, FlowParam]
    steps: tuple[FlowStep, ...]
    hash: str                        # flow_hash of the parsed file (32 hex)
    origin: str                      # "git" | "override"
```

`origin` is set by the loader. The core never reads it for a decision.

## Pure functions (`core/flows.py`)

| Function | Purpose |
|---|---|
| `validate_flow(data, stem, vocab) -> list[str]` | Rules 1 to 15 of [contracts/flow-template.md](contracts/flow-template.md). Fixed error sentences. |
| `parse_flow(data, origin, vocab) -> Flow` | Build a `Flow` from valid data. Computes `hash`. Raises `ValueError` when `validate_flow` is not empty. |
| `flow_hash(data) -> str` | First 32 hex characters of SHA-256 of the canonical JSON. |
| `Flow.matches(steps, cards, starter) -> bool` | The shape check ([contracts/plan-source.md](contracts/plan-source.md) "Shape"). Spec 003 `effective_source` calls it. |
| `parse_flow_mention(text, agent_users) -> FlowMention \| None` | [contracts/flow-mention.md](contracts/flow-mention.md). It extends `flow_word(text)` of spec 003 with parameters and agent mentions. |
| `missing_tags(flow, params, cards) -> list[str]` | Sorted tags of the flow that no trusted card offers (`matches_tag` of spec 003). For a `$agent` step: the tags that the named card does not offer. |
| `expand_flow(flow, mention, cards, starter) -> tuple[list[dict], list[str]]` | Plan steps and errors. Deterministic. Calls no LLM. The planner receives it as the injected `expand` of spec 003. |
| `build_plan(flow, steps) -> dict` | `{"steps": steps, "source": "template:<name>@<hash>"}`. The core sets the source. The LLM never writes it. |
| `validate_tags(data)`, `parse_tags(data)` | The tag vocabulary ([contracts/tag-vocabulary.md](contracts/tag-vocabulary.md)). |

All functions are pure. They do not change their input. They read no tag name: tags are opaque strings.

## Functions of spec 003 that spec 006 uses (NOT defined here)

Spec 006 defines none of these. The old copies in `core/flows.py` are removed. Each name points to its home in spec 003.

| Name | Home (spec 003) | Use in 006 |
|---|---|---|
| `effective_source(plan, flows, cards, starter)`, `hop_limit(source)`, `parse_source`, `MAX_HOP_FREE = 3`, `MAX_HOP_TEMPLATE = 5` | `core/source.py` | The source check and the `hop` limit. `flows` is a map of `Flow` (006). |
| `validate_plan(plan, cards, starter=None, flows=None)` | `core/pipeline.py` | The plan check, with the limit by source and the new step fields. |
| `claim_excluded(plan, thread, i, agent_id)` | `core/claim.py` | `exclude_agents_of` at run time. |
| `exclusion_deadlock(plan, cards)`, `branch_target(plan, i, reason)`, `next_step(plan, thread, i)`, `gate_pending(thread, i)`, `open_question(thread)`, `dialog_expired(question_ts, now, hours)`, `step_rejected(thread, i)` | `core/pipeline.py` | The structure rules, the branch, the gate, the dialog. |
| `flow_word(text)` | `core/route.py` | The explicit `flow:<name>` word. |
| `effective_payload(step_payload, results)` | `core/runrequest.py` | The context for the next step. |
| Route actions `plan_flow`, `release`, `resume`, `expire_dialog` | `core/route.py` | Used as they are. |

The rules for the gate state, the branch (`on_fail`, type 11), the dialog (type 10, `dialog_timeout`), the release (a new type 5 `done`), and the route are in [../003-chat-pipelines/data-model.md](../003-chat-pipelines/data-model.md) and [../003-chat-pipelines/contracts/task-metadata.md](../003-chat-pipelines/contracts/task-metadata.md). This file does not repeat them.

## FlowMention

```python
@dataclass(frozen=True)
class FlowMention:
    name: str
    params: Mapping[str, str]
    goal: str
    agents: tuple[str, ...]     # agent IDs named after the planner, in text order
```

## Planner call changes

Spec 003 `run_planner` takes the injected `expand` (here `expand_flow` with `build_plan`) and the list of valid templates (`name`, `description`). For the `plan_flow` action (an explicit `flow:` word, or a trigger with `flow:`) the planner makes no runtime call. For free text, the LLM may return only `{"flow": "<name>"}`. The core expands it.

## Messages

No new message type. The plan message (type 1) text shows the source line: `Flow: bugfix (template)` or `Flow: none (free plan)`. The text is a hint. The check is `effective_source`.
