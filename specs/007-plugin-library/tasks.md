---

description: "Task list for the Shared Plugin Library"
---

# Tasks: Shared Plugin Library

**Input**: [spec.md](spec.md), [plan.md](plan.md)

**Tests**: Tests are required (constitution principle VII). Each test task comes BEFORE its implementation task. The test must fail first. Tests use fake directories. They never read the real `~/.claude`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel.
- **[Story]**: US1 to US3 from [spec.md](spec.md).
- Status: `[x]` means done in the first pass.

---

## Phase 1: Library skeleton (US1, US2)

- [x] T001 [US1] Create `pipe-library/.claude-plugin/marketplace.json` with the name `pipe-library` and two plugins (FR-001)
- [x] T002 [P] [US1] Create `plugins/review-helpers/` (`plugin.json`, `README.md`, skill `prepare-review`, tag `review`, `allowed-tools: Read, Grep, Glob`) (FR-002, FR-003)
- [x] T003 [P] [US1] Create `plugins/trigger-tools/` (`plugin.json`, `README.md`, skill `post-trigger`, same tools, no script) (FR-002, FR-003, FR-009)
- [x] T004 [P] [US1] Create `CODEOWNERS` with a placeholder owner (FR-004)
- [x] T005 [US1] Create `.gitlab-ci.yml` with the jobs: validate marketplace, validate plugins, eval (only with `evals/`), secret scan, tag check (FR-005 to FR-008)
- [x] T006 [US2] Create `README.md`: add the marketplace, install, pin, update, add a plugin (FR-016)
- [x] T007 [US1] Run `claude plugin validate --strict` on the marketplace and on each plugin. Fix the findings (SC-001)
- [ ] T008 [US1] Test the CI secret scan and the tag check on a copy with a fake token and a wrong tag (SC-005)
- [ ] T009 [US1] Add the release note job for `#pipe-library` (FR-017). The webhook comes from a CI variable
- [ ] T010 [US1] Replace `<OWNER>` and `<GIT_URL>`. Make the real repository (owner action)

---

## Phase 2: Owner-only rule in the adapter (US3)

**Goal**: A library item is `owner-only` unless it is in `exposed`.

### Tests first (they MUST fail)

- [x] T011 [P] [US3] Write failing test in `tests/unit/test_config.py` for `library_marketplaces`: default `[]`, valid names, invalid values; the error names the key and not the value (FR-010)
- [x] T012 [P] [US3] Write failing test in `tests/unit/test_runtime_claude_discovery.py`: the plugin key gives `marketplace`; a personal item has none (FR-011)
- [x] T013 [P] [US3] Write failing test in `tests/unit/test_runtime_claude_exposure.py`: `classify` and `to_core` with a library marketplace, with another marketplace, with no marketplace, and with an empty list (FR-012)
- [x] T014 [P] [US3] Write failing test in `tests/integration/test_adapter_capabilities.py` with a fake tree: a clean library skill is `owner-only` and not in the card; the same ID in `exposed` is exposed; a skill from another marketplace stays exposed; an empty list changes nothing; a step denies an unexposed library skill (FR-013, FR-014, SC-002, SC-003)

### Implementation

- [x] T015 [US3] Add `library_marketplaces` to `src/pipe/config.py` (T011)
- [x] T016 [US3] Add `marketplace` to `src/pipe/runtime_claude_capability.py` and set it in `src/pipe/runtime_claude_discovery.py` (T012)
- [x] T017 [US3] Add the `library` argument to `classify` and `to_core` in `src/pipe/runtime_claude_exposure.py` (T013)
- [x] T018 [US3] Pass `library_marketplaces` in `src/pipe/capset.py`, `src/pipe/runtime_claude_loadset.py`, and `src/pipe/runtime_claude_request.py` (T014)
- [x] T019 [P] [US3] Add `library_marketplaces` to `docs/reference.md`
- [x] T020 [US3] Add `marketplace` to the forbidden literals in `tests/unit/test_core_boundary.py`; it is forbidden in `src/pipe/core/` (FR-015, SC-004)

---

## Phase 3: Polish

- [x] T021 Run `make ci`. All tests and the lint must pass
- [ ] T022 Do one manual run with a real library repository, a real install, and a real owner config (owner action)

## Dependencies

- T011 to T014 before T015 to T018.
- T008 and T009 need the real CI. T010 comes before T022.
