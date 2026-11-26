# Implementation Plan: Review Capability and External Triggers

**Branch**: `005-review-gitlab-triggers` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-review-gitlab-triggers/spec.md`

## Summary

A review step is a normal step. Its capability has the tag `review`. The step uses `capability: "tag:review"`. The core has no review code. The claim rule, the timeout, and the "Retry" button come from spec 003. A step ends when its agent posts `status: done`. For a slow capability, the claiming adapter keeps the step `running` until its capability implementation ends. Then the adapter posts `status: done` or `status: failed`. No message from another source counts. So no new trust path exists. The first review implementation is wiz-review. The owner declares it in the config as a capability, tags it `review`, and exposes it. A small wrapper script sends one review request and waits for the drafts (DQ1 = a). The wrapper needs no change in wiz-review. The wrapper contract is general: an e2e run or a long test run uses the same output (`text`, `status`, `artifacts`, `data`, `files`). A wrapper that prints `{status: failed}` and exits 0 takes the `on_fail` branch of spec 003. The adapter uploads the `files` with `Transport.upload_file`.

A trigger bot is a Slack bot with a card of `kind: trigger` and no skills. It posts a top-level mention in `#pipe-work`. The mention carries EITHER a fixed `pipeline` in the metadata `pipe.task.v1` OR the word `flow:<name>` with a goal in the text (DQ3). The mentioned agent is the planner. It checks the trigger with the new pure function `parse_trigger`. A `flow:` trigger goes through the `plan_flow` action of spec 003 (no LLM). It checks the plan with `validate_plan(plan, cards, starter, flows)` (003). Then the new pure function `decide_trigger` uses `in_allowlist` (004). `allow`: the adapter posts the plan and the start handoff with no ✅. `ask`: the adapter posts the plan with the buttons Accept and Reject (the buttons of spec 004). Only the owner of the mentioned agent can click. After the start, it is a normal pipeline. The CI template is a stdlib script `post_trigger.py` and a CI job file. GitLab CI is the first example (`pipe-gitlab`).

New core code is small: one core module (`trigger.py`), a few rules in `pipeline.py`, `route.py`, and `render.py`. `effective_payload` is spec 003 code and 005 does not change it. The rest is three template files and tests. Details: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.15 (same as 001 to 004).

**Primary Dependencies**: `slack_bolt`, `pyyaml` (from 001). Test-only: `pytest`. No new dependency. The templates use the standard library only (`json`, `urllib.request`, `hashlib`, `os`, `argparse`). See "New dependencies" below.

**Storage**: No new file under `~/.pipe/` and no new state. The thread messages hold the trigger state. The CI template reads its settings from environment variables.

**Testing**: `pytest`. Pure functions have unit tests first, with no Slack and no LLM: `parse_trigger`, `decide_trigger`, `validate_plan` (trigger bot as step agent), `route` (trigger, accept/reject on a plan, duplicate handoff, not the claimant, Wake, `flow:` trigger), `render_task` (trigger texts), `upload_run_files`, `build_trigger_message`, `build_card`, and the wrapper helpers. The import-boundary test of 003 (T071) globs every core module, so `trigger.py` is covered. Task T003 adds the 005 terms. Slack and the runtime sit behind ports with fakes (`FakeTransport`, `FakeRuntime`). One manual run with real Slack, a real GitLab schedule, and real wiz-review is in [quickstart.md](quickstart.md).

**Target Platform**: macOS laptop for the adapter (same as 001). The trigger script runs in any CI runner that has Python 3 and no extra package.

**Project Type**: Extension of the 001 to 004 background process (`pipe run`). No new CLI command. The trigger script is a separate stdlib file.

**Performance Goals**: A trigger gives a started pipeline in under 2 minutes (SC-005). A hung review step shows `failed` less than one minute after the time limit (SC-009).

**Constraints**: No server, no database, no web UI. The core names no wiz-review, no GitLab, and no review term (principle XI). The CI job holds the trigger token in a masked CI variable only. No MCP URL, token, or local path enters a card (the trigger card has no skills). One runtime call at a time per adapter (001). The `hop` limit follows the plan source: 3 for a free plan, 5 for a verified template (003). The Slack scope `files:write` is new for the adapter (spec 001); the trigger bot needs `chat:write` and `pins:write` only.

**Scale/Scope**: 3 to 6 developers. A few trigger runs per day.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.3.0.

| Principle | Pre-research | Post-design | Note |
|---|---|---|---|
| I. No Server in the MVP | PASS | PASS | GitLab CI is the scheduler. The trigger is one Slack post from a CI job. The trigger state is in the thread. No database and no service. |
| II. The Owner Controls the Agent | PASS | PASS | The owner of the mentioned agent decides: the allowlist or the accept/reject button. Only that owner clicks. The owner exposes the review capability. |
| III. Discovered Is Not Exposed | PASS | PASS | A wiz-review capability uses the credentials of the owner. It is `owner-only` until the owner exposes it. The trigger card has no skills. |
| IV. Every Change Goes Through an MR | PASS | PASS | A review step is `read`. A `write` step in a trigger pipeline follows spec 004 (worktree, MR). The trigger template pushes no code. |
| V. Thread Content Is Untrusted Input | PASS | PASS | Metadata counts only from a bot with a card. A trigger mention counts only from a card of `kind: trigger`. A completion counts only from the claiming agent (FR-008). Clicks count only from the owner. |
| VI. Runtime-Agnostic Contract | PASS | PASS | The runtime contract does not change. A slow capability is the work of a capability adapter behind the contract. The runtime knows no trust and no Slack. |
| VII. Business Rules Are Pure Functions | PASS | PASS | `parse_trigger`, `decide_trigger`, the new route rules, and the new plan rule are pure. Test tasks come before implementation tasks. |
| VIII. Reuse Before Build | PASS | PASS | Reuses claim, timeout, "Retry", `Wake`, `in_allowlist`, the 004 buttons, the 003 plan check and start handoff, the 002 card shape and `validate_card`. Review reuses wiz-review through a wrapper. The wrapper copies no wiz-review code. |
| IX. Small Dependencies | PASS | PASS | No new dependency. |
| X. STE for All Written Artifacts | PASS | PASS | All artifacts use STE. |
| XI. Core Is Capability-Agnostic | PASS | PASS | The only new core module is `core/trigger.py`. It uses opaque IDs and the card kind. The core has no review term. The tag `review` is data in the config and in the plan. wiz-review sits in `templates/review/` outside the package. GitLab sits in `templates/trigger/gitlab-ci.yml`. The import-boundary test gets the terms `wiz`, `gitlab`, and `review` (T003). It also forbids the standard tag names as constants (constitution 1.3.0). |

Technology and Security Constraints: tokens in Keychain for the adapter (PASS: no new adapter token). The trigger token is a masked CI variable and is never in a file (PASS: FR-023, T026, T028, T030). Scrub before post (PASS: the trigger script and the adapter scrub every text and reason). Cards hold no MCP URL, token, or path (PASS: `build_card` output passes `validate_card`). `hop` by plan source (PASS: the trigger has `hop` 0). Core uses the `Transport` port only (PASS: `upload_file`, T036).

**Result**: PASS. No deviation. No Complexity Tracking row. The design decisions DQ1 to DQ9 are in "Design decisions". One question (O1) is open. The tasks follow the recommended option.

## Design decisions

The owner confirmed these decisions on 2026-11-26 (pass 2). The tasks follow them. Each decision lists the affected tasks.

**DQ1 = (a). A config-declared wrapper polls.** The capability is declared in the owner config. Its wrapper sends one request, then waits or polls until the work ends, then exits. The adapter posts the result. No change in wiz-review. No new trust path. The step time limit covers the wait. The wrapper contract is not review-only: it serves review, e2e, long tests, and any long task (`contracts/slow-capability.md`). Affected tasks: T012, T013, T014, T015, T036, T037.

**DQ2 = (a). Context through `effective_payload(step_payload, results)`.** The core gives the capability the `context` (a list of `{step, text, artifacts}`) and the `artifacts` (all links) of ALL earlier done steps (spec 003 FR-037, N2). A plan `payload` key wins. `check_input` validates the effective payload, so a schema with `additionalProperties: false` must list `context` and `artifacts`. This replaces the old `effective_payload(step_payload, prev_artifacts)`. Affected tasks: T007, T008, T010.

**DQ3. A trigger carries EITHER a fixed `pipeline` OR `flow:<name>` text with a goal.** A fixed `pipeline` is checked with `validate_plan`. A `flow:<name>` text is expanded with the `plan_flow` action of spec 003 (a deterministic expansion, spec 006 DQ8 = a). Both together give `bad_payload`. Neither gives `bad_payload`. A free goal text with no flow word is not allowed for a trigger. `parse_trigger(msg, cards, flow)` gets the flow name from `flow_word` of spec 003 (the route computes it, so `trigger.py` imports no route code). Affected tasks: T016, T017, T020, T021, T024, T025, T026, T027.

**DQ4 = (a). No cap on trigger starts.** The owner removes the bot from the allowlist and rotates the token. `max_budget_usd` (001) and the `hop` limit (3 free, 5 template) bound the cost. A cap by count (option b) is a later change. Affected tasks: none.

**DQ5 = (a). Keep spec 004.** The first handoff of an allowlisted trigger pipeline comes from the planner. The planner bot ID is not in its own allowlist, so a `write` step for it asks the owner. The owner can add the own bot ID to the allowlist. Affected tasks: none (quickstart documents it).

**DQ6 = (a). The global step time limit.** `step_timeout_min` covers a slow capability. The owner raises it when needed. A "Retry" resumes the wait without a second request (FR-012). Affected tasks: T012, T014.

**DQ7 = (a). No dedupe of a CI retry.** Two threads start. Slack `event_id` dedupe (001) drops a repeated event only. Affected tasks: none.

**DQ8. Closed by `exclude_agents_of`.** The planner and the templates set `exclude_agents_of` on a review step (spec 003 FR-039, N4). The claim rule ignores a claim from an agent that holds an excluded step. Spec 005 adds no rule. Affected tasks: T008.

**DQ9 = (a). One runtime slot.** A review that waits blocks the other mentions of that adapter (001: one runtime call at a time). Add parallel capabilities later if the metrics show a delay. Affected tasks: T015.

**Transport and files.** The core uses the `Transport` port only (no Slack in the core). The adapter uploads the files of a wrapper with `Transport.upload_file` (scope `files:write`, 10 MB, regular file in `~/.pipe/run/`, no symbolic link, else `UploadRefused`). Affected tasks: T036, T037.

## Open design question (pass 2, not decided)

- **O1. Who reports the files of a wrapper?** The runtime output of spec 001 has no field for files. This spec adds the optional output field `files` (list of paths) for the `exec` adapter. The stepper (outside the core) uploads them and appends the links to `artifacts`. Options: (a) the optional field `files` in the `exec` output, as written here (small, additive; needs one line in spec 001 `runtime-exec-http.md`); (b) the wrapper puts the paths in `data` and the stepper reads a convention (hidden coupling); (c) no upload, and the wrapper prints only links (needs a file host that the owner does not have). Recommendation: (a). The tasks T036 and T037 follow (a).

## Changes to 001 to 004

005 makes these changes. Each has a task. All other model changes of the old list exist in 001 to 004 after pass 1 (late binding: 003 T084, T085; payload and context: 003 T100, T101; payload check: 003 T075; `starter`: 003 `ThreadState.starter`; declared capabilities: 002; `Transport` and `upload_file`: 001).

1. **003 `route` and `step_status`** (T005, T006): a handoff and a `done` count only from the bot that holds the winning claim. A later handoff for the same step is ignored (`duplicate_handoff`, `not_claimant`). If 003 already has these rules when T005 runs, T006 is removed.
2. **003 `contracts/task-metadata.md`**: the buttons `pipe_accept` and `pipe_reject` also apply to a type 1 plan message of a trigger thread. Pass 2 adds one sentence to that contract. The click rule is the same as in 004 `contracts/gate.md`. 005 `contracts/trigger-message.md` states it.
3. **002 card `kind`**: `kind` is `agent` or `trigger`. A `trigger` card has `skills: []` and `mode: ci`. Pass 2 adds one sentence to 002 `contracts/card.md`. `validate_card` has no `kind` rule, so it accepts the card (T026 tests it).
4. **001 runtime output `files`** (O1): one optional field `files` in the `exec` output. Open until the owner confirms O1.
5. **Brief §9 M4 and §12**: no text change. The owner of the reviewer agent owns the wrapper config.

## Project Structure

### Documentation (this feature)

```text
specs/005-review-gitlab-triggers/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── trigger-message.md
│   └── slow-capability.md
├── checklists/requirements.md
└── tasks.md             # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

New files are marked `+`. Changed 001 to 004 files are marked `~`.

```text
src/pipe/
├── core/                            # PURE functions only
│   ├── trigger.py           +       # parse_trigger(msg, cards, flow) -> Trigger | None; decide_trigger(sender, allowlist) -> Gate
│   ├── pipeline.py          ~       # validate_plan: a step agent with a card of kind trigger is an error; handoff_ok(thread, msg): first handoff and claimant only
│   ├── route.py             ~       # Trigger decision; accept/reject on a trigger plan; Wake for a trigger parent; duplicate_handoff and not_claimant
│   └── render.py            ~       # texts of the trigger request and of the reject
├── stepper.py               ~       # start_trigger, accept_plan, reject_plan (reuse start and gate buttons); upload_run_files (Transport.upload_file)
└── adapter.py               ~       # top-level bot messages in the work channel go to route; block_actions for the plan message

templates/                           # outside the package. Stdlib only. Not imported by the core
├── trigger/
│   ├── post_trigger.py      +       # build_trigger_message, build_card, post; CLI: `card` and `post`
│   └── gitlab-ci.yml        +       # first CI template: job with variable names only
└── review/
    ├── wiz_review_capability.py +   # wrapper: one request, wait for the drafts, JSON result (the output contract also fits e2e and long tasks)
    └── config.example.yaml  +       # declared capability, tags map, exposed list (no secret)

tests/
├── unit/                            # test_trigger.py, test_route_trigger.py, test_post_trigger.py, test_wiz_review_capability.py
│                                    # (+ changes to test_route_bot.py, test_validate_plan.py, test_runrequest.py, test_render.py, test_core_boundary.py)
├── fakes.py                 ~       # FakeRuntime hold/release; make_card(kind="trigger"); make_trigger_message
├── integration/                     # test_review_step.py, test_async_completion.py, test_trigger_flow.py
└── manual/                          # none new
```

**Structure Decision**: Single project, same layout as 001 to 004. The new rules sit in `core/` as pure functions. Slack sits behind the `Transport` port. The wiz-review wrapper and the CI template sit in `templates/`, outside the package, so the core cannot import them.

## New dependencies

None. Each template uses the Python standard library only.

| Item | Reason |
|---|---|
| `urllib.request` (stdlib) in `post_trigger.py` | One HTTPS call to the Slack Web API from a CI job. A CI runner needs no `pip install`. |
| `hashlib`, `json` (stdlib) in `post_trigger.py` | The card `hash` of an empty skills list. A unit test checks that it equals the core hash (T026). |
| `pytest` (test-only, from 001) | Tests. |

## Complexity Tracking

No constitution deviation. No row.
