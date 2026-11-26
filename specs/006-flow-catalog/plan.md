# Implementation Plan: Flow Catalog

**Branch**: `006-flow-catalog` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-flow-catalog/spec.md`

## Summary

A flow template is a YAML file in `flows/` (shared, in git) or in `~/.pipe/flows/` (owner override, wins by name). A template has only tag steps. It names no agent, plugin, or tool. A person starts it with `@agent flow:<name> <goal>`, or the planner picks a template name from the free text. The core expands the template into a normal plan with no LLM. The plan needs ✅ (or the trigger gate of spec 005). Every `write` step still meets the owner gate of spec 004.

A plan records its `source`: `template:<name>@<hash>` or `free`. The LLM never writes it. The source sets the `hop` limit: 5 for a verified template, 3 for a free plan (constitution 1.3.0). The source is only a claim. Every adapter recomputes the effective source from its own template files (`effective_source` of spec 003, `core/source.py`): same name, same hash, and a matching step shape. A mismatch, an unknown name, a stale copy, or a human edit gives `free` (DQ1 = b).

The pure core module `core/flows.py` holds template data rules only: the template check, the hash, the mention parser, the expansion, the missing-tag check, `Flow.hash` and `Flow.matches(steps, cards, starter)`. The rules for the source, the `hop` limit, `exclude_agents_of`, `gate: approval`, `on_fail`, the dialog, and the release are spec 003 code (`core/source.py`, `core/pipeline.py`, `core/claim.py`, `core/route.py`). Spec 006 has no duplicate of them. A thin loader (`flows_io.py`) reads the files. A standard tag vocabulary is data in `flows/tags.yaml`. Ten flows are YAML files from [contracts/flow-catalog.md](contracts/flow-catalog.md). Most of the work is data and tests. No new dependency.

## Technical Context

**Language/Version**: Python 3.15 (same as 001 to 005).

**Primary Dependencies**: `slack_bolt`, `pyyaml` (from 001). Test-only: `pytest`. No new dependency. YAML loading uses `pyyaml` that the project already has (DQ2). Hash: `hashlib` and `json` from the standard library.

**Storage**: No new state. Template files only: `flows/*.yaml` (git) and `~/.pipe/flows/*.yaml` (owner). The adapter never writes them. The thread messages hold the flow state.

**Testing**: `pytest`. Pure functions have unit tests first, with no chat, no LLM, and no disk: `validate_flow`, `parse_flow`, `flow_hash`, `parse_flow_mention`, `missing_tags`, `expand_flow`, `Flow.matches`, `validate_tags`, and `render_task` (the source line). The 003 functions (`effective_source`, `hop_limit`, `next_step`, `branch_target`, `claim_excluded`, `exclusion_deadlock`, `validate_plan`, `route`) are tested in spec 003. Spec 006 tests them again only through the real templates (catalog and integration tests). The loader has tests with `tmp_path`. A catalog test expands all ten files with fake cards. Integration tests use `FakeTransport` and `FakeRuntime` (acceptance tests of the user stories). One manual check covers the planner choice of a template with a real LLM, and one manual run covers feature-dev with real agents ([quickstart.md](quickstart.md)).

**Target Platform**: macOS laptop (same as 001).

**Project Type**: Extension of the 001 to 005 background process (`pipe run`) and CLI (new `pipe flows`).

**Performance Goals**: Template expansion for one mention takes less than 50 ms (11 small files, no LLM). A hop check for a handoff reads the files and takes less than 50 ms.

**Constraints**: No server, no database, no web UI. The core names no tag, plugin, review tool, GitLab, or chat product (principle XI). The core does no file I/O. A template holds no token, MCP URL, or local path. Steps run one by one. No loop. At most one conditional step.

**Scale/Scope**: 3 to 6 developers. Ten flows. A few flows per day.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.3.0.

| Principle | Pre-research | Post-design | Note |
|---|---|---|---|
| I. No Server in the MVP | PASS | PASS | Templates are files. State is in the thread. No service, no database. |
| II. The Owner Controls the Agent | PASS | PASS | The owner chooses which capabilities get tags (`tags` map) and which are exposed. The override file is the owner's. The adapter never writes a template. |
| III. Discovered Is Not Exposed | PASS | PASS | A tag counts only when a card offers it. An `owner-only` capability is not in the card, so its tag is missing. |
| IV. Every Change Goes Through an MR | PASS | PASS | `implement` and `spec` are `write` steps. They use the worktree and MR of spec 004. No template pushes to `main`. |
| V. Thread Content Is Untrusted Input | PASS | PASS | The plan `source` is untrusted text. Every receiver recomputes it. ✅ counts only from the starter or the planner owner. A dialog reply counts only from an allowed person (DQ7). |
| VI. Runtime-Agnostic Contract | PASS | PASS | The runtime contract does not change. A template step is a normal capability call. |
| VII. Business Rules Are Pure Functions | PASS | PASS | Template check, expansion, source check, and branch rules are pure. Test tasks come before implementation tasks. |
| VIII. Reuse Before Build | PASS | PASS | Reuses `matches_tag`, `bind_step`, the claim rule, `validate_plan`, the gates of 004 and 005, `Wake`, and `scrub`. Adds data files, not engines. |
| IX. Small Dependencies | PASS | PASS | No new dependency. `pyyaml` is in the stack. |
| X. STE for All Written Artifacts | PASS | PASS | All files use STE. Template `description` and `goal` texts use STE. |
| XI. Core Is Capability-, Runtime-, and Transport-Agnostic | PASS | PASS | `core/flows.py` handles opaque tag strings. The vocabulary is data (DQ3). The loader sits outside the core. The boundary test globs every core module and forbids the standard tag names (003 T071, 006 T003). |

Technology and Security Constraints: tokens in the Keychain (PASS: no new token). Scrub before post (PASS: the planner scrubs the goal text). Cards hold no MCP URL, token, or path (PASS: no card change). `hop` limit by plan source, 3 or 5 (PASS: constitution 1.3.0 allows 5 for a verified template; every adapter recomputes the source).

**Result**: PASS. No deviation. No Complexity Tracking row. The twelve design decisions are in "Design decisions".

## Design decisions

The owner confirmed all twelve decisions on 2026-11-26 (pass 2). The tasks follow them. The numbers DQ1 to DQ12 are the ones of this spec. Spec 003 uses N1 to N13 for the same points.

- **DQ1 = (b). Source check by recompute.** Every adapter recomputes the effective source from its own template files: same name, same hash, matching shape. A mismatch gives `free`. Spec 003 N7 holds the code (`core/source.py`: `effective_source`, `hop_limit`, `parse_source`, `MAX_HOP_FREE`, `MAX_HOP_TEMPLATE`). Spec 006 supplies `Flow.hash` and `Flow.matches(steps, cards, starter)`. Tasks: T021, T023, T024, T062.
- **DQ2 = (a). YAML.** `yaml.safe_load` with `pyyaml` (already in the stack). Tasks: T010, T017.
- **DQ3 = (a). The tag vocabulary is data** in `flows/tags.yaml`. Tasks: T003, T005, T006.
- **DQ4 = (a). The planner picks a name.** The LLM returns only `{"flow": "<name>"}` (at most 32 characters). The core expands the template (003 N10). Tasks: T013, T019, T060.
- **DQ5 = (a). Branch only on `run_failed`.** `run_failed` is only a runtime result with `status: failed`. A non-zero exit of `exec` gives `RuntimeFailed` and no branch. Tasks: T038, T039, T055 (the rules are in 003 T108, T109).
- **DQ6 = (a). The mid-flow gate** is a type 5 `needs_approval` message with a ✅ release (003 N3). Tasks: T027, T030, T046 (the rules are in 003 T102 to T105).
- **DQ7 = (a). A dialog answer** counts only from the thread starter or the agent owner, and it needs a mention of the agent (003 N1, U3). Tasks: T046 (the rules are in 003 T094 to T099).
- **DQ8 = (a). A trigger carries `flow:<name> <goal>`** and no `pipeline` (spec 005 DQ3). Both together give `bad_payload`. Tasks: T034, T035, T036.
- **DQ9 = (a). `delegate`:** the second agent mention fills `$agent`. Tasks: T052 to T054.
- **DQ10 = (a). Two copies of a template** give `free` on the adapter with the other copy. The thread fails closed with `hop limit exceeded (plan source not verified)`. Tasks: T022, T023, T062.
- **DQ11 = (a). A free plan may use `gate`, `on_fail`, and `exclude_agents_of`.** The limit stays 3 (003 N6). Tasks: T012, T022.
- **DQ12 = (a). An approved proposal is context only**, in a template and in a free plan (003 N3, U2 = a). The source does not change. A proposal never replaces the remaining steps. Tasks: T030, T046.

Pass 2 closes the old item "DQ8 of spec 005" (self-review): `exclude_agents_of` is set by the planner and by the templates on review steps (003 N4).

## Changes needed

No change is left. The old list of 25 items is done: the constitution (1.3.0: `hop` by source, tag vocabulary is data), spec 003 (second batch N1 to N13), spec 001 (`Transport.upload_file`, `pipe flows [show <name> | validate [<name>]]` dispatch with `flows_handler(action, name)`), spec 005 (trigger with `flow:`, `effective_payload` with all results), and the brief (decisions 18 to 20, M5). One old item is obsolete: the planner schema `maxItems` stays 4 (LLM plans only). A template path has no LLM steps, so it needs no larger `maxItems`.

006 only needs the handler for `flows_handler(action, name)` (T020) and the `expand` function that the 003 planner receives (T019).

## Project Structure

### Documentation (this feature)

```text
specs/006-flow-catalog/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── flow-template.md
│   ├── tag-vocabulary.md
│   ├── flow-mention.md
│   ├── plan-source.md
│   ├── flow-catalog.md
│   └── cli.md
├── checklists/requirements.md
└── tasks.md             # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

New files are marked `+`. Changed files of earlier specs are marked `~`.

```text
src/pipe/
├── core/                            # PURE functions only
│   ├── flows.py             +       # validate_flow, parse_flow, flow_hash, Flow (hash, matches(steps, cards, starter)), parse_flow_mention, missing_tags, expand_flow, build_plan, validate_tags. NO copy of the 003 functions (effective_source, hop_limit, next_step, branch_target, claim_excluded, exclusion_deadlock)
│   └── render.py            ~       # the plan source line only (`Flow: bugfix (template)`). The other 003 texts are in 003
├── flows_io.py              +       # load_flows(shared_dir, override_dir) -> (flows, errors); load_tags(path); no writes
├── planner.py               ~       # injects expand_flow/build_plan as the `expand` of the 003 planner (plan_flow, output `flow`)
├── cli.py                   ~       # `flows_handler(action, name)` for `pipe flows [show <name> | validate [<name>]]` (001 owns the dispatch)
└── adapter.py               ~       # ThreadState.flows through flows_io.py

flows/                               # data, in git (not in the package)
├── tags.yaml            +
├── feature-dev.yaml     +
├── bugfix.yaml          +
├── planning.yaml        +
├── brainstorm.yaml      +
├── research.yaml        +
├── test-run.yaml        +
├── troubleshoot.yaml    +
├── review-handoff.yaml  +
├── delegate.yaml        +
└── nightly.yaml         +

tests/
├── unit/                            # test_flows_validate.py, test_flows_mention.py, test_flows_expand.py, test_flows_source.py, test_flows_branch.py, test_flows_io.py, test_flows_tags.py, test_flow_catalog.py
│                                    # (+ changes to test_route_*.py, test_validate_plan.py, test_render.py, test_core_boundary.py)
├── fakes.py                 ~       # make_flow_cards, write_flow, FakeTransport.upload_file, FakeRuntime needs_input
├── integration/                     # test_flow_start.py, test_flow_source.py, test_flow_<name>.py (one per flow story)
└── manual/                          # none new (see quickstart.md)
```

**Structure Decision**: Single project, same layout as 001 to 005. The pure rules sit in `core/flows.py`. The file reads sit in `flows_io.py`. The flows are data in `flows/`, outside the package.

## New dependencies

None. `pyyaml` is already in the stack (constitution IX).

| Item | Reason |
|---|---|
| `yaml.safe_load` (`pyyaml`, existing) in `flows_io.py` | Reads templates and the vocabulary. The config format is YAML already. |
| `hashlib`, `json`, `re` (stdlib) in `core/flows.py` | The source hash and the mention parser. |
| `pytest` (test-only, from 001) | Tests. |

## Complexity Tracking

No constitution deviation. No row. (Constitution 1.3.0 allows the `hop` limit of 5 for a verified template.)
