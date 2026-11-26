---

description: "Task list for Flow Catalog"
---

# Tasks: Flow Catalog

**Input**: Design documents from `/specs/006-flow-catalog/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md. Specs 001 to 005 are implemented, with their second batch (constitution 1.3.0): the functions of spec 003 `core/source.py`, `core/pipeline.py`, `core/claim.py`, and `core/route.py` (`effective_source`, `hop_limit`, `claim_excluded`, `exclusion_deadlock`, `branch_target`, `next_step`, `gate_pending`, `open_question`, `dialog_expired`, `step_rejected`, `flow_word`), `Transport.upload_file`, and the `flow:` trigger of spec 005. Spec 006 defines none of these functions.

**Tests**: Tests are required. Constitution principle VII (NON-NEGOTIABLE): every pure-function business rule has a test task BEFORE its implementation task. The test must fail first. Tests use fakes: no real chat product, no real LLM, no network. Acceptance tests of the flow stories run the planner path with fake cards and `FakeTransport`, with no LLM, except where a task says "manual check".

**Organization**: Tasks are grouped by user story. Paths follow the Source Code layout in [plan.md](plan.md). The tasks follow the owner decisions in "Design decisions" of plan.md (DQ1 to DQ12, all confirmed) and constitution v1.3.0 principle XI. If the owner changes a decision, change the tasks that plan.md lists for it.

**Changes to earlier files**: 006 changes few files of 003 and 005 (the planner `expand` wiring, the render source line, the adapter `flows`). Each such task says "change" and names the earlier task.

**Removed tasks (pass 2)**: The tasks that duplicated spec 003 or spec 005 code are marked `[x]` with the text "Removed in pass 2": T011, T022, T025, T027, T028, T031, T032, T034, T036, T038, T040. Their IDs stay so that no ID changes. They need no work. The test and the code are in spec 003 (T090 to T115) and spec 005 (T016 to T025). The 006 tests of the real templates stay.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US12, from [spec.md](spec.md)
- Test tasks start with "Write failing test" or "Change the test".
- In each story, the test tasks come first. The implementation tasks follow.

## Path Conventions

Single project: `src/pipe/`, `tests/unit/`, `tests/integration/`, `tests/fakes.py`, and `flows/` at the repository root (same as 001 to 005). The flows are data files outside the package.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the files. Check the baseline.

- [ ] T001 Create the empty new files from the plan: `src/pipe/core/flows.py`, `src/pipe/flows_io.py`, and the directory `flows/`
- [ ] T002 Run `pytest tests/unit tests/integration` for specs 001 to 005. All tests must pass before 006 work starts. Check that these parts exist in the code (all are planned in specs 001 to 005): tag steps, `matches_tag`, `check_input` (003 T075, T084, T085); `core/source.py` with `effective_source`, `hop_limit`, `parse_source` (003 T090 to T093); the dialog with `needs_input`, `open_question`, `dialog_expired`, `dialog_timeout_h` (003 T094 to T099); `effective_payload(step_payload, results)` (003 T100, T101); the gate and the proposal with `gate_pending` and the `release` action (003 T102 to T105); `claim_excluded` and `exclusion_deadlock` (003 T106, T107); `branch_target`, `next_step`, and type 11 (003 T108, T109); `flow_word`, `plan_flow`, and the planner `flow` output with an injected `expand` (003 T110, T111); `step_rejected` (003 T114, T115); `Transport.upload_file` (001 T059, T060); the `pipe flows` dispatch with `flows_handler(action, name)` (001 T061, T062); `effective_deny_rules` (001); `parse_trigger(msg, cards, flow)` and the trigger `flow:` path (005 T016, T017, T025). All parts exist in the specs, so this task is a check, not a stopper by default. If a part is missing in the code, stop and list the exact IDs that are missing. Do not add the part in a 006 task. Do not add a Python dependency

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The boundary test, the fakes, and the tag vocabulary. Every story needs them.

**CRITICAL**: No user story work starts before this phase is complete.

- [ ] T003 [P] Change the import-boundary test in `tests/unit/test_core_boundary.py` (003 T071, 004 T017, 005 T003; FR-032, SC-010, principle XI). Write failing cases:
  - The list of core modules gets `flows.py`. The test first checks that `src/pipe/core/flows.py` exists (T001).
  - The list of forbidden terms gets the standard tag names that are not common words: `e2e`, `reproduce`, `brainstorm`, `troubleshoot`, `deps-check`, `decompose`, `diagnose`, `playwright`. (The terms `review`, `wiz`, and `gitlab` are already in the list from 005.) A term matches a whole word inside an identifier or a string constant. Comments and docstrings are not read.
  - The test reads `flows/tags.yaml` when it exists and checks that the forbidden list covers every tag name that is not in a small allow list of common words (`implement`, `context`, `research`, `summarize`, `spec`, `collect`). The check fails when someone adds a tag with a rare name and forgets the test.
  - The list of forbidden imports gets `yaml` for the module `core/flows.py` (the core reads no file) and any module under `flows_io`.
  - A negative case: a temporary core module with the string constant `"e2e"` makes the checker report an error.
  - Check by hand that the existing core modules hold none of the new terms. A hit is a finding to fix in that module, not in the test.
- [ ] T004 [P] Extend `tests/fakes.py` (FR-004, FR-026):
  - `make_flow_cards(tags_by_agent)`: builds trusted cards. Each agent gets one capability per tag with `tags=[tag]` and an `access` from a small map (`implement` and `spec` are `write`, the rest `read`). Cards for the `write` tags use the `claude` runtime; cards for `read` tags may use `exec`.
  - `write_flow(dir, name, data)`: writes a template YAML into a `tmp_path` directory.
  - `FakeTransport.upload_file` records `(channel, thread, name)` and returns a fixed link. (If T002 shows that it exists, only add the helper that reads the record.)
  - `FakeRuntime` can return `needs_input` for a step once, and a result `status: failed` (`run_failed`) for a step. It can also raise `RuntimeFailed("exit 1")`.
  - `make_human_message(text, mentions)` builds a top-level `HumanMessage` with agent mentions.
- [ ] T005 [P] Write failing test in `tests/unit/test_flows_tags.py` (FR-013, FR-014; DQ3). Cases for `validate_tags` and `parse_tags`: a valid file; a bad key; `access` other than `read` or `write`; an empty or long `meaning`; a wrong `version`. A second test reads the real file `flows/tags.yaml` and checks that it has exactly the 14 tags of [contracts/tag-vocabulary.md](contracts/tag-vocabulary.md) with the default access of that table
- [ ] T006 Implement `validate_tags` and `parse_tags` in `src/pipe/core/flows.py` (T005). Write `flows/tags.yaml` from [contracts/tag-vocabulary.md](contracts/tag-vocabulary.md)

**Checkpoint**: Foundation ready. User stories can start.

---

## Phase 3: User Story 1 - Start a flow by name (Priority: P1) MVP

**Goal**: `@agent flow:<name> <goal>` gives a plan from a template with no LLM call. A missing tag is reported by name. The plan needs ✅.

**Independent Test**: Run `tests/integration/test_flow_start.py`. It uses a temporary template file, fake cards, `FakeTransport`, and a `FakeRuntime` that fails the test when it is called.

### Tests for User Story 1 (write first, they MUST fail)

- [ ] T007 [P] [US1] Write failing test in `tests/unit/test_flows_mention.py` (FR-006, FR-007; [contracts/flow-mention.md](contracts/flow-mention.md)). Cases for `parse_flow_mention`: a plain `flow:name goal`; parameters `key=value`; the first `flow:` word only; a `flow:` word in the middle of the goal; a bad name; a bad key or value; no `flow:` word gives `None`; two mentions give `agents`; the mentions are removed from the goal; an empty goal; an uppercase `Flow:` is not a flow word; white space is made single; the function does not change its input
- [ ] T008 [P] [US1] Write failing test in `tests/unit/test_flows_validate.py` (FR-002, FR-003, FR-005, FR-014, FR-015, FR-033; [contracts/flow-template.md](contracts/flow-template.md)). One case for each of the 15 rules, with the exact error sentence. Include: an unknown key; a name that differs from the stem; a concrete agent ID in `agent`; a tag that is not in the vocabulary; an `access` that differs from the tag default; two `$agent` steps; a human step that is not last; `exclude_agents_of` to a later step; two `on_fail` steps; `on_fail` to a step that is not last; `on_fail` with a human step; a loop (`on_fail` to an earlier step); six agent steps; a `://` string; an absolute path; a token-like string; an unused parameter; a parameter value that is not a tag. Also test `flow_hash`: the same data in another key order gives the same hash; one changed character gives another hash; the hash has 32 hex characters
- [ ] T009 [P] [US1] Write failing test in `tests/unit/test_flows_expand.py` (FR-008, FR-011; [contracts/flow-template.md](contracts/flow-template.md) "Expansion"). Cases for `missing_tags`, `expand_flow`, and `build_plan`: all tags offered gives steps and no errors; two missing tags give one error with both names, sorted; an `owner-only` capability (not in the card) counts as missing; an access that does not fit counts as missing; `{goal}` replacement; a goal over 500 characters gives `goal too long`; `$starter` gives `human:<id>`; ids become indexes for `exclude_agents_of` and `on_fail`; parameter default, a given value, a bad value, an unknown key; `tag:$check` becomes the tag; the result is the same for the same input; the input is not changed; `build_plan` adds `source: template:<name>@<hash>`. (The `$agent` cases are in T052.)
- [ ] T010 [P] [US1] Write failing test in `tests/unit/test_flows_io.py` with `tmp_path` (FR-001, FR-004, FR-005, FR-010; DQ2). Cases for `load_flows` and `load_tags`: a valid shared file; a valid override; the override wins by name; an invalid override does not hide a valid shared file (the error is reported); a file over 20 000 bytes is refused; a YAML tag that builds an object (`!!python/object`) is refused; a file whose `name` differs from the stem is invalid; a missing shared directory loads the override only; a non-`.yaml` file is ignored; the loader writes no file (the directory listing and the modification times are the same after the call); each flow has `origin`
- [x] T011 [US1] Removed in pass 2. The route rule for `plan_flow` (`flow:` word, first named agent is the planner, a thread reply is `chat`, a "save this flow" message is `chat`) is tested in spec 003 T110 (`flow_word`, `plan_flow`). Spec 006 keeps only the integration cases in T013. No work here
- [ ] T012 [P] [US1] Change the test of `render_task` in `tests/unit/test_render.py` (003 T011; FR-032). Write failing cases: the plan text shows `Flow: bugfix (template)` for a verified template plan and `Flow: none (free plan)` for a free plan; the line is a hint only; no path, token, or URL enters the text. The structure rules of the step fields (`exclude_agents_of`, `gate`, `on_fail` in `validate_plan`, also for a free plan, DQ11) are tested in spec 003 (T106, T108, T016). No 006 test duplicates them
- [ ] T013 [P] [US1] Write failing test in `tests/integration/test_flow_start.py` with `FakeTransport`, two cards, and a `FakeRuntime` that fails when it is called (SC-001 to SC-003, SC-011, SC-012). Scenarios: (1) `flow:bugfix` with all tags: a plan message with `source` and `needs_approval`, zero runtime calls, no step starts; ✅ from the starter starts step 0; ✅ from another person changes nothing. (2) The override wins. (3) An unknown name: a type 2 message with the known names. (4) Missing tags: a type 2 message `flow feature-dev: missing tags: e2e, review`, and ✅ starts nothing. (5) One agent and `flow:` counts as a pipeline request. (6) A free-text message with a runtime output `{"flow": "bugfix"}` expands the template (the runtime is called once for the planner only). (7) A runtime output with an unknown `flow` gives `could not build a plan`. (8) A runtime output with `flow` and `steps` uses the template and ignores `steps`. (9) A message "save this as a flow" writes no file in the flows directories
- [ ] T014 [P] [US1] Write failing test in `tests/unit/test_cli_flows.py` (FR-031; [contracts/cli.md](contracts/cli.md)). Test `flows_handler(action, name)` with `action` `list`, `show`, and `validate` (001 owns the parser). Cases: the list shows name, origin, the first 12 characters of the hash, the needed tags, and the missing tags; an invalid file shows `-` and the reason, with exit code 1; `override (hides git)`; `show <name>` shows the steps and the full hash; `validate` prints `OK` or `FAIL` for each file, and with a name all errors of that file; an unknown name gives exit code 2; no file is written

### Implementation for User Story 1

- [ ] T015 [US1] Implement `validate_flow`, `parse_flow`, `flow_hash`, `Flow`, and `parse_flow_mention` in `src/pipe/core/flows.py` (T007, T008; same file as T006). Pure. No file I/O. The `scrub` check of rule 14 uses the `scrub` function that the core already has
- [ ] T016 [US1] Implement `missing_tags`, `expand_flow`, and `build_plan` in `src/pipe/core/flows.py` (T009; same file as T015). Reuse `matches_tag` of 003
- [ ] T017 [P] [US1] Implement `src/pipe/flows_io.py` (T010; DQ2): `load_tags(path)`, `load_flows(shared_dir, override_dir, vocab) -> (flows, errors)`. Use `yaml.safe_load`. Refuse a file over 20 000 bytes. The loader opens files for reading only. The shared directory comes from `flows_dir` or the default
- [ ] T018 [US1] Change `render_task` in `src/pipe/core/render.py` (T012; same file as 003 T012): add the source line. `validate_plan` is spec 003 code and 006 does not change it
- [ ] T019 [US1] Change `src/pipe/planner.py` and `src/pipe/adapter.py` (T013; same files as 003 T111 and 005 T025): pass `expand_flow` and `build_plan` as the injected `expand` of the 003 planner, pass the template list (`name`, `description`) to the planner prompt data, and build `ThreadState.flows` through `flows_io.py` at each plan. The `plan_flow` route action, `flow_word`, and the planner `flow` output are spec 003 code (T110, T111). Do not add them here
- [ ] T020 [US1] Implement `flows_handler(action, name)` in `src/pipe/cli.py` (T014; FR-031). Read-only. Use `load_flows`, the card cache, `validate_flow`, and `missing_tags`. Spec 001 T062 owns the parser and the dispatch. Register the handler there

**Checkpoint**: A flow starts from a mention with no LLM call. Missing tags show by name. US1 passes its own tests.

---

## Phase 4: User Story 2 - Source and hop limit (Priority: P1)

**Goal**: A plan records its source. Every adapter recomputes it. The limit is 5 for a verified template and 3 for the rest.

**Independent Test**: Run `tests/unit/test_flows_source.py` and `tests/integration/test_flow_source.py`.

### Tests for User Story 2 (write first, they MUST fail)

- [ ] T021 [P] [US2] Write failing test in `tests/unit/test_flows_source.py` (FR-020, FR-021; DQ1; [contracts/plan-source.md](contracts/plan-source.md)). The logic of `effective_source` and `hop_limit` is spec 003 (T090, with a fake flow). This test checks the real `Flow` of spec 006: `Flow.hash` is the `flow_hash` of the parsed file. `Flow.matches(steps, cards, starter)` is true for the expansion of `build_plan`; false for one extra step, one removed step, a changed tag, access, order, `gate`, `on_fail`, or `exclude_agents_of`; true for a changed `goal`, `payload`, or `target`; for `tag:$check` true for each allowed value and false for another value; for a `$agent` step true when the card has the tag and false when it lacks it; false for a human step of another user; the override template is used by name. Also call spec 003 `effective_source` with real `Flow` objects: the plan from `build_plan` gives `template`, a different hash gives `free`, an unknown name gives `free`, and a bad `source` string gives `free` with no exception. The inputs are not changed
- [x] T022 [US2] Removed in pass 2. The cases for `hop` 4, 5, and 6, the refusal text `hop limit exceeded (plan source not verified)`, and the agent-step limit by source are tested in spec 003 (T090 to T093, T016, T027). No work here
- [ ] T023 [P] [US2] Write failing test in `tests/integration/test_flow_source.py` with `FakeTransport` and two adapters that have different `flows/` copies (SC-004, SC-005; DQ1, DQ10). Scenarios: (1) a verified `feature-dev` runs to `hop` 4 on two adapters. (2) A planner whose override has another hash: the receiver refuses at `hop` 4 with the unverified text. (3) A person edits the plan (the planner posts a new plan message with the steps changed): the new message has `source: free`. (4) A forged plan message from a bot with a card, with a template source and 5 other steps, is refused at `hop` 4. (5) A change of one `goal` text only keeps `template`. (6) A receiver with no `flows/` directory refuses at `hop` 4 with the unverified text

### Implementation for User Story 2

- [ ] T024 [US2] Implement `Flow.hash` and `Flow.matches(steps, cards, starter)` in `src/pipe/core/flows.py` (T021; same file as T016). `effective_source`, `hop_limit`, `MAX_HOP_FREE`, and `MAX_HOP_TEMPLATE` are spec 003 (`core/source.py`, T091). Do not define them here
- [x] T025 [US2] Removed in pass 2. `validate_plan(plan, cards, starter, flows)` and the `route` hop check by source are spec 003 code (T093). No work here
- [ ] T026 [US2] Check that the planner sets `source` only through `build_plan` (the core sets it, the LLM never writes it, and a plan that is not from `build_plan` has `free`), in `src/pipe/planner.py` (T023; same file as T019). Run `tests/integration/test_flow_source.py`. Spec 003 T093 holds the refusal text and the limit

**Checkpoint**: The limit follows the effective source. A forged or stale claim gives 3.

---

## Phase 5: User Story 3 - feature-dev (Priority: P1)

**Goal**: The flow `feature-dev` runs with the approval gate after `decompose` and the exclusion of the implementer from `review`.

**Independent Test**: Run `tests/integration/test_flow_feature_dev.py`.

### Tests for User Story 3 (write first, they MUST fail)

- [x] T027 [P] [US3] Removed in pass 2. The gate state (`gate_pending`, ✅ `release`, the trigger-owner rule, no handoff before ✅) is tested in spec 003 (T102, T103, T114). The feature-dev integration test T030 checks it through the real template. No work here
- [x] T028 [P] [US3] Removed in pass 2. `claim_excluded`, `exclusion_deadlock`, and `ignore(excluded)` are tested in spec 003 (T106). The feature-dev integration test T030 checks them through the real template. No work here
- [ ] T029 [P] [US3] Write failing test in `tests/unit/test_flow_catalog.py` (FR-029, SC-001). A parametrized test that loads each file in `flows/` with `load_flows`, expands it with `make_flow_cards` (all tags offered), runs `validate_plan`, and checks `effective_source` is `template`. The table has one row for `feature-dev` now: 4 agent steps, 1 human step, the tags in order, `decompose` has `gate`, `review` excludes `implement`. Each later story adds its row
- [ ] T030 [P] [US3] Write failing test in `tests/integration/test_flow_feature_dev.py` with `FakeTransport`, three agents, and `FakeRuntime` (SC-003, SC-007, SC-008). Run the whole flow: plan, ✅, `decompose` done with a proposal (the thread is `needs_approval`, no handoff), ✅, `implement` (the 004 gate asks when the agent has another owner), `e2e` (the fake agent calls `upload_file` for a report and a screenshot, and the links are in `artifacts`), `review` (the claimant of `implement` cannot claim it; another agent claims it), the approval button, `done`. Check `hop` 4 is accepted. Check the case with only one agent that offers `review` and `implement`: the plan is rejected before ✅ (certain deadlock). Check that a `review` with no other agent ends `no_claimer` when two agents offer `implement` and only one offers `review`

### Implementation for User Story 3

- [x] T031 [US3] Removed in pass 2. The gate state, the ✅ rule, and the `release` action are spec 003 code (T103, T105). No work here
- [x] T032 [US3] Removed in pass 2. `claim_excluded`, `exclusion_deadlock`, and the `ignore(excluded)` rule are spec 003 code (T107). No work here
- [ ] T033 [US3] Write `flows/feature-dev.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/unit/test_flow_catalog.py` and `tests/integration/test_flow_feature_dev.py`

**Checkpoint**: feature-dev runs end to end with fakes.

---

## Phase 6: User Story 4 - bugfix (Priority: P1)

**Goal**: The flow `bugfix` runs from chat or from an issue trigger. A failing test comes first.

**Independent Test**: Run `tests/integration/test_flow_bugfix.py`.

### Tests for User Story 4 (write first, they MUST fail)

- [x] T034 [P] [US4] Removed in pass 2. The trigger forms (`flow:<name> <goal>` with no `pipeline`, both forms give `bad_payload`, neither gives `bad_payload`) are tested in spec 005 (T016, T020, T024). No work here
- [ ] T035 [P] [US4] Write failing test in `tests/integration/test_flow_bugfix.py` and add the `bugfix` row to `tests/unit/test_flow_catalog.py` (T029). Scenarios: (1) chat: expand, 4 agent steps, 1 human step, the tags in order. (2) An allowlisted trigger bot posts `flow:bugfix <issue text>`: the planner expands the template, posts the plan, and starts with no ✅ and no button. (3) A trigger bot that is not in the allowlist: the owner gets the button, no step starts. (4) `reproduce` ends `failed`: `implement` does not start, a "Retry" button shows. (5) The `implement` step meets the 004 gate. (6) A missing tag `reproduce` is reported by name

### Implementation for User Story 4

- [x] T036 [US4] Removed in pass 2. `parse_trigger(msg, cards, flow)` and the `flow:` trigger path are spec 005 code (T017, T021, T025). The trigger sends the `flow` to the 003 `plan_flow` path (T019 here wires `expand`). No work here
- [ ] T037 [US4] Write `flows/bugfix.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_bugfix.py`

**Checkpoint**: bugfix runs from chat and from a trigger.

---

## Phase 7: User Story 5 - test-run (Priority: P2)

**Goal**: The flow `test-run` runs e2e and branches to `troubleshoot` only on `run_failed`.

**Independent Test**: Run `tests/unit/test_flows_branch.py` and `tests/integration/test_flow_test_run.py`.

### Tests for User Story 5 (write first, they MUST fail)

- [x] T038 [P] [US5] Removed in pass 2. `branch_target`, `next_step`, the type 11 checks, `bad_branch`, and `already_branched` are tested in spec 003 (T108). The test-run integration test T039 checks them through the real template. No work here
- [ ] T039 [P] [US5] Write failing test in `tests/integration/test_flow_test_run.py` with `FakeTransport`, two agents, and `FakeRuntime` (spec US5). Scenarios: (1) success: the report and the screenshot go through `upload_file`, the links are in `artifacts`, the thread is `done`, `troubleshoot` never starts. (2) `run_failed`: `troubleshoot` starts once with the payload of step 1 (`text` and `artifacts`), the flow ends after it. (3) `timeout` of e2e: no branch, `failed` and a "Retry" button. (4) `no_claimer` for `e2e`: no branch. (5) `troubleshoot` fails: `failed` and a "Retry" button, and no further step. (6) A "Retry" on a failed e2e that branched: no button exists. (7) A wrapper result `status: failed` with exit code 0 branches. A wrapper that exits with a non-zero code gives `RuntimeFailed`, "Retry", and no branch (spec 005 FR-025). Add the `test-run` row to `tests/unit/test_flow_catalog.py`

### Implementation for User Story 5

- [x] T040 [US5] Removed in pass 2. The branch rules, the type 11 post (no "Retry" button), and the texts are spec 003 code (T109). The wrapper rule (`{status: failed}` with exit code 0 takes the branch, a non-zero exit does not) is spec 005 `contracts/slow-capability.md`. No work here
- [ ] T041 [US5] Write `flows/test-run.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_test_run.py`

**Checkpoint**: The branch works and the flow ends after it.

---

## Phase 8: User Story 6 - troubleshoot (Priority: P2)

**Goal**: The flow `troubleshoot` collects data, diagnoses, fixes in an MR, and asks for approval.

**Independent Test**: Run `tests/integration/test_flow_troubleshoot.py`.

- [ ] T042 [P] [US6] Write failing test in `tests/integration/test_flow_troubleshoot.py` and add the `troubleshoot` row to `tests/unit/test_flow_catalog.py` (T029). Scenarios: (1) expand: 3 agent steps, 1 human step, tags `collect`, `diagnose`, `implement`. (2) An allowlisted alert trigger bot posts `flow:troubleshoot <alert>`: the pipeline starts with no ✅. (3) `collect` returns a file through `upload_file` and a link: `diagnose` gets the artifacts. (4) `collect` ends `done` with `no data`: `diagnose` ends `failed` with a reason. (5) `implement` for another owner meets the 004 gate. (6) A large text result goes by link: the thread text stays short (the payload text is cut at the limit of 003)
- [ ] T043 [US6] Write `flows/troubleshoot.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_troubleshoot.py`

---

## Phase 9: User Story 7 - review-handoff (Priority: P2)

**Goal**: The flow `review-handoff` reviews, fixes, and reviews again.

**Independent Test**: Run `tests/integration/test_flow_review_handoff.py`.

- [ ] T044 [P] [US7] Write failing test in `tests/integration/test_flow_review_handoff.py` and add the `review-handoff` row to `tests/unit/test_flow_catalog.py` (T029). Scenarios: (1) expand: 3 agent steps, 1 human step, `re-review` excludes `implement`. (2) The first review gives a drafts link. `implement` gets it in its payload. (3) The agent of `implement` cannot claim `re-review`. (4) The pass pattern A (review), B (implement), A (review) is allowed by the back-and-forth rule of 003 FR-010. (5) A fake slow review (held `FakeRuntime`) keeps the step `running` until release (spec 005 rule). (6) An MR event trigger posts `flow:review-handoff <MR link>` and the MR link is in the goal
- [ ] T045 [US7] Write `flows/review-handoff.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_review_handoff.py`

---

## Phase 10: User Story 8 - planning (Priority: P2)

**Goal**: The flow `planning` runs a dialog, writes a spec, and ends with a task proposal and ✅.

**Independent Test**: Run `tests/integration/test_flow_planning.py`.

- [ ] T046 [P] [US8] Write failing test in `tests/integration/test_flow_planning.py` and add the `planning` row to `tests/unit/test_flow_catalog.py` (T029) (FR-027, FR-028, SC-009; DQ6, DQ7). Scenarios: (1) expand: 3 agent steps, no human step, `decompose` has `gate`. (2) `brainstorm` returns `waiting` with `needs_input`. A reply from the starter resumes the same step on the same agent. `hop` is unchanged and no new claim exists. (3) A reply from a person who is not the starter or the owner of the agent does not resume the step. A reply from the starter that does not mention the agent does not resume it either (003 U3). (4) While the step waits, the step timer does not fire. After `dialog_timeout_h` the step is `failed` with `reason: dialog_timeout` and a "Retry" button. (5) `spec` is a `write` step and meets the 004 gate. (6) `decompose` returns a proposal that fails `validate_plan`: the step ends `failed` with the errors. (7) A valid proposal makes the thread `needs_approval`. ✅ ends the flow (`done`) and starts no work. (8) An approved proposal is context only (DQ12 = a): the remaining steps and the source stay, and no step is replaced
- [ ] T047 [US8] Write `flows/planning.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_planning.py`. The dialog rule is spec 003 code (T094 to T099). Do not add it in this task

---

## Phase 11: User Story 9 - brainstorm (Priority: P3)

**Goal**: The flow `brainstorm` collects context, runs a dialog, and keeps a summary.

**Independent Test**: Run `tests/integration/test_flow_brainstorm.py`.

- [ ] T048 [P] [US9] Write failing test in `tests/integration/test_flow_brainstorm.py` and add the `brainstorm` row to `tests/unit/test_flow_catalog.py` (T029). Scenarios: (1) expand: 3 agent steps, all `read`, no human step. (2) `context` returns links: `brainstorm` gets them. (3) `context` ends `done` with `no context found`: the dialog still starts. (4) The dialog resumes as in T046. (5) `summarize` gets the `text` of both previous steps and ends with a document link from `upload_file`. (6) No `write` step exists, so the 004 gate never asks
- [ ] T049 [US9] Write `flows/brainstorm.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_brainstorm.py`

---

## Phase 12: User Story 10 - research (Priority: P3)

**Goal**: The flow `research` searches and keeps a document.

**Independent Test**: Run `tests/integration/test_flow_research.py`.

- [ ] T050 [P] [US10] Write failing test in `tests/integration/test_flow_research.py` and add the `research` row to `tests/unit/test_flow_catalog.py` (T029). Scenarios: (1) expand: 2 agent steps, both `read`. (2) `summarize` gets the links of `research`. (3) The final document goes through `upload_file`. (4) A missing tag `research` is reported by name when the web capability is not exposed. (5) A step that exceeds the time limit is `failed` with `timeout` and a "Retry" button
- [ ] T051 [US10] Write `flows/research.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_research.py`

---

## Phase 13: User Story 11 - delegate (Priority: P3)

**Goal**: The flow `delegate` sends a `write` step to the agent that the person names.

**Independent Test**: Run `tests/unit/test_flows_expand.py` (the `$agent` cases) and `tests/integration/test_flow_delegate.py`.

- [ ] T052 [P] [US11] Write failing test for `$agent` in `tests/unit/test_flows_expand.py` (T009) and `tests/integration/test_flow_delegate.py` (FR-002, DQ9). Unit cases: the second mention fills `$agent`; the step has the agent ID and the lowest capability ID of that card with the tag and a fitting access; a card without the tag gives `flow delegate: missing tags: implement`; no second mention gives `flow delegate needs a second agent mention`; a flow without `$agent` and an extra mention gives `flow <name> takes no agent mention`; the named agent is not trusted: the plan is rejected. Integration: (1) `@coder-pavlo @coder-bob flow:delegate <goal>`: the plan has the fixed step for `coder-bob`, `write` access. (2) The 004 gate gives `ask` when `coder-pavlo` is not in the allowlist of `coder-bob`, and the button appears. (3) The 004 gate gives `allow` when both conditions of 004 FR-005 hold. (4) The template source does not change either result. (5) The result is an MR link in `artifacts`. Add the `delegate` row to `tests/unit/test_flow_catalog.py` (T029)
- [ ] T053 [US11] Implement the `$agent` resolution in `expand_flow` and `missing_tags` in `src/pipe/core/flows.py` (T052; same file as T016). Use the lowest-ID rule of `bind_step`
- [ ] T054 [US11] Write `flows/delegate.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_delegate.py`

---

## Phase 14: User Story 12 - nightly (Priority: P3)

**Goal**: The flow `nightly` runs a check from a CI schedule with the parameter `check`.

**Independent Test**: Run `tests/integration/test_flow_nightly.py`.

- [ ] T055 [P] [US12] Write failing test in `tests/integration/test_flow_nightly.py` and add the `nightly` row to `tests/unit/test_flow_catalog.py` (T029) (DQ5, DQ8). Scenarios: (1) an allowlisted trigger bot posts `flow:nightly`: the tag is `e2e`, the pipeline starts with no ✅. (2) `flow:nightly check=deps-check`: the tag is `deps-check`. (3) `check=lint`: the plan is rejected with `flow nightly: bad value for check`. (4) A failed check with `run_failed` branches to `troubleshoot`. A timeout does not. (5) The report goes through `upload_file`. (6) A trigger bot that is not in the allowlist: the owner gets the button. (7) The same schedule posted twice starts two threads (spec 005 DQ7)
- [ ] T056 [US12] Write `flows/nightly.yaml` from [contracts/flow-catalog.md](contracts/flow-catalog.md). Run `tests/integration/test_flow_nightly.py`

---

## Phase 15: Polish & Cross-Cutting Concerns

- [ ] T057 Run `pytest tests/unit/test_core_boundary.py tests/unit/test_core_purity.py` (SC-010; 003 T064 and T071, 005 T029). `core/flows.py` must hold no I/O import, no `yaml` import, and no forbidden term. Fix the finding in the module, not in the test
- [ ] T058 [P] Check that no new file under `src/`, `tests/`, `flows/`, and `specs/006-flow-catalog/` holds a token, an MCP URL, or a local path (FR-033, SC-013). Search for `xox`, `xapp`, `glpat`, `Bearer `, `/Users/`, and `://` in `flows/` (skip `tasks.md` and `contracts/`, which name these strings). Check that each template `goal` and `description` is STE (short, active, no idiom)
- [ ] T059 Change the test `tests/unit/test_flow_catalog.py` (T029; SC-001, SC-011). Add the completeness cases: `flows/` has exactly the ten template files of [contracts/flow-catalog.md](contracts/flow-catalog.md) and `tags.yaml`; each file has at most 5 agent steps; every tag in every file is in the vocabulary; removing one tag card gives `flow <name>: missing tags: <tag>`; the files are not changed by any test run (modification times). Run it and fix the files
- [ ] T060 Manual check (needs a real LLM): ask the planner in free text, for example "fix the login bug and test it". Check that it returns `flow: bugfix` (DQ4). Try five requests that match no template. Check that none gets a template. Write the result in quickstart.md section 3
- [ ] T061 Manual check on a real chat workspace with two or three adapters: run `feature-dev` from a mention to the final approval. Check the ✅ gate after `decompose`, the exclusion at `review`, `hop` 4, and the artifacts from `upload_file`. Measure the time from the mention to the plan message (target: under 5 seconds, no LLM)
- [ ] T062 Manual check of DQ1 and DQ10 with two checkouts: change one character in `flows/bugfix.yaml` in one checkout. Run `bugfix` from the other adapter. Check that the refusal at `hop` 4 shows `plan source not verified`, and that `pipe flows` on both sides shows two different hashes
- [ ] T063 Run `pytest tests/unit tests/integration` and fix failures (quickstart section 1). Then tick the items of `checklists/requirements.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependency.
- Foundational (Phase 2): needs Phase 1. It blocks all user stories.
- US1 (Phase 3): needs Phase 2. It blocks every flow story (the engine).
- US2 (Phase 4): needs US1. T024 needs T016.
- US3 (Phase 5): needs US2 (the limit 5 for `feature-dev`). The gate and the exclusion are spec 003 code.
- US4 (Phase 6): needs US1 and US2. The trigger path is spec 005 code (T025).
- US5 (Phase 7): needs US1 and US2. The branch is spec 003 code (T109).
- US6, US7, US9, US10 (Phases 8, 9, 11, 12): need US3 and US2. They add data and tests only.
- US8 (Phase 10): needs US3 (the gate). The dialog rule comes from spec 003 (T002).
- US11 (Phase 13): needs US1. T053 needs T016.
- US12 (Phase 14): needs US5 (the branch) and US4 (the trigger text, spec 005 T025).
- Polish (Phase 15): needs all stories.

### Within Each User Story

- Test tasks come first and MUST fail before the implementation task.
- Pure functions in `src/pipe/core/` before the I/O code that calls them.
- Tasks that edit the same file are not marked [P]: `core/flows.py` (T006, T015, T016, T024, T053), `render.py` (T018), `planner.py` (T019, T026), `adapter.py` (T019), `tests/fakes.py` (T004), `tests/unit/test_flow_catalog.py` (T029, T035, T039, T042, T044, T046, T048, T050, T052, T055, T059).
- Test-first pairs: T005 before T006. T007 and T008 before T015. T009 before T016. T010 before T017. T013 before T019. T012 before T018. T014 before T020. T021 before T024. T023 before T026. T029 and T030 before T033. T035 before T037. T039 before T041. T052 before T053.
- T003 changes a 003, 004, and 005 test. It needs `flows.py` to exist (T001).
- T002 is a check. If it finds a missing part, stop and list the IDs.

### Parallel Opportunities

- Phase 2: T003, T004, and T005 together.
- US1 tests T007 to T010, T012, T013, and T014 together. T017 beside T015 and T016 (different file).
- US2 tests T021 and T023 together.
- US3 tests T029 and T030 together.
- After US3: US4, US5, US6, US7, US9, US10, and US11 can run with different developers. They share `tests/unit/test_flow_catalog.py`, so the catalog rows merge at the end.
- Data tasks T033, T037, T041, T043, T045, T047, T049, T051, T054, and T056 each write one file and can run together after their tests exist.

---

## Parallel Example: User Story 1

```text
# Launch all tests together:
Task: "Write failing test for parse_flow_mention in tests/unit/test_flows_mention.py"
Task: "Write failing test for validate_flow and flow_hash in tests/unit/test_flows_validate.py"
Task: "Write failing test for expand_flow and missing_tags in tests/unit/test_flows_expand.py"
Task: "Write failing test for the loader in tests/unit/test_flows_io.py"
Task: "Write failing test in tests/integration/test_flow_start.py"

# Then the implementation in order:
Task: "Implement validate_flow, flow_hash, parse_flow_mention in src/pipe/core/flows.py"
Task: "Implement missing_tags, expand_flow, build_plan in src/pipe/core/flows.py"
Task: "Implement src/pipe/flows_io.py"
Task: "Change pipeline.py, render.py, route.py, planner.py, adapter.py"
Task: "Implement pipe flows"
```

---

## Implementation Strategy

### MVP First (User Stories 1 to 3)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1), Phase 4 (US2), and Phase 5 (US3): a flow starts from a mention, the limit follows the verified source, and `feature-dev` runs with fakes. Stop and validate: tests pass, then quickstart scenarios 1 to 4.

### Incremental Delivery

1. Add US4 (bugfix and the trigger text). Validate.
2. Add US5 to US7 (branch, troubleshoot, review-handoff). Validate.
3. Add US8 to US12 (planning, brainstorm, research, delegate, nightly). Most of the work is a data file and a test.
4. Polish: manual checks with a real LLM, a real chat workspace, and two checkouts.

### Traceability

- FR-001: T008, T010, T017. FR-002: T008, T052. FR-003: T008. FR-004: T010, T017. FR-005: T008, T010. FR-006: T007, T013 (and 003 T110). FR-007: T007, T013, T019, T060. FR-008: T009, T013, T016. FR-009: T013, T030, T035, T052. FR-010: T010, T011, T013. FR-011: T009, T013, T016. FR-012: T004 (fake cards use the `tags` map shape), T061. FR-013: T003, T005, T006. FR-014: T005, T008. FR-015: T008, T039 (and 003 T108). FR-016: T039 (and 003 T108, 005 T012). FR-017: T030 (and 003 T106). FR-018: T030 (and 003 T102). FR-019: T008 (no parallel field in the schema), T030. FR-020: T008, T009, T021. FR-021: T021, T023, T024. FR-022: T021, T023 (and 003 T090 to T093). FR-023: T023, T026. FR-024: T023 (and 003 T093). FR-025: T030, T039, T042, T044, T048, T050. FR-026: T030, T039, T042, T048, T050, T055. FR-027: T046. FR-028: T030, T046. FR-029: T029, T059. FR-030: T059 (no status-sync file). FR-031: T014, T020. FR-032: T003, T057. FR-033: T008, T058. FR-034: T035, T055 (and 005 T016 to T025).
- SC-001: T029, T059. SC-002: T009, T013. SC-003: T013, T030, T035. SC-004: T021, T023 (and 003 T090). SC-005: T021, T023. SC-006: T039 (and 003 T108). SC-007: T030 (and 003 T106). SC-008: T030 (and 003 T102). SC-009: T046. SC-010: T003, T057. SC-011: T010, T013, T059. SC-012: T010. SC-013: T058. SC-014: T003, T057. SC-015: T046.
- User stories: US1 (T007 to T020), US2 (T021 to T026), US3 (T027 to T033), US4 (T034 to T037), US5 (T038 to T041) (the removed IDs have no work), US6 (T042, T043), US7 (T044, T045), US8 (T046, T047), US9 (T048, T049), US10 (T050, T051), US11 (T052 to T054), US12 (T055, T056).
- Design decisions (all confirmed): DQ1 (T021, T023, T024, T026, T062; the code is 003 T090 to T093), DQ2 (T010, T017), DQ3 (T003, T005, T006), DQ4 (T013, T019, T060), DQ5 (T039, T041, T055; the code is 003 T108, T109), DQ6 (T030, T046; the code is 003 T102 to T105), DQ7 (T046; the code is 003 T094 to T099), DQ8 (T035, T055; the code is 005 T016 to T025), DQ9 (T052 to T054), DQ10 (T023, T062), DQ11 (T012; the code is 003), DQ12 (T030, T046).
- Reuse: `matches_tag`, `bind_step`, the claim rule, `validate_plan`, `scrub`, `Wake`, the ✅ rule, and `no_claimer` of 003. The gate of 004. `in_allowlist`, `decide_trigger`, the slow-capability rule, and the duplicate-handoff rule of 005. The config `tags` map of 002. `Transport.upload_file` of 001.

---

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Verify that each test fails before you write the implementation.
- Do not commit from these tasks without an explicit owner request.
- If the owner changes a design decision, change the tasks listed for that decision in the Traceability section.
