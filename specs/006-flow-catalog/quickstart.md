# Quickstart: Validate the Flow Catalog

Use this guide after implementation. It proves the user stories. It holds no implementation code. Specs 001 to 005 must be installed and working (`pipe doctor` passes, the cards are in `#pipe-agents`, a chat pipeline, a delegation run, and a trigger run work).

## Prerequisites

- Three adapters: `coder-pavlo` (owner Pavlo), `coder-bob` (owner Bob), and `reviewer-olena` (owner Olena). Each has a card.
- Each owner gave tags to capabilities with the config map `tags`, and exposed them. Together the team offers these tags: `decompose`, `implement`, `e2e`, `review`, `reproduce`, `brainstorm`, `context`, `research`, `summarize`, `spec`, `collect`, `diagnose`, `troubleshoot`, and `deps-check`. At least two agents offer `implement` and at least two offer `review`.
- Every team member has the same checkout of the git repository with `flows/`. Run `pipe flows` on each laptop. The hash column must be equal. `pipe flows validate` checks all files and prints the errors.
- The trigger bot `pipe-gitlab` exists (spec 005). Its ID is in the allowlist of `coder-pavlo` for the trigger scenarios.

## 1. Unit and integration tests (no chat, no LLM, no network)

```text
pytest tests/unit tests/integration
```

Expected: all pass. Covers SC-001 to SC-013 with fakes. The import-boundary test (SC-010) and the catalog test (SC-001) are part of it.

## 2. Scenarios (real chat)

| Story | Steps | Expected |
|---|---|---|
| 1 | Run `pipe flows`. | Ten templates in the list. The `MISSING` column is `-` on every line. |
| 1 | Pavlo writes in `#pipe-work`: "@coder-pavlo flow:bugfix the login page returns 500". | A plan message appears in under 5 seconds. It shows `Flow: bugfix (template)` and `needs_approval`. No step runs. |
| 1 | Pavlo adds ✅. | Step 1 (`reproduce`) starts. |
| 1 | Write "@coder-pavlo flow:nope test". | A rejected plan with the known flow names. |
| 1 | Stop the adapter that offers `e2e`. Write `flow:feature-dev add a field`. | A rejected plan: `flow feature-dev: missing tags: e2e`. |
| 1 | Write "@coder-pavlo save this plan as a flow". | A normal chat reply. No file changes in `flows/` or `~/.pipe/flows/`. |
| 2 | Run `feature-dev` to the review step. | The `hop` reaches 4. No refusal. |
| 2 | On one laptop, change one character in `flows/bugfix.yaml` and run `bugfix` from the other laptop. | The thread stops at `hop` 4 with `hop limit exceeded (plan source not verified)`. `pipe flows` shows two hashes. |
| 3 | Run `feature-dev`. After `decompose` ends, look at the thread. | The thread shows `needs_approval`. Step 2 does not start. |
| 3 | A person other than Pavlo adds ✅. | Nothing changes. |
| 3 | Pavlo adds ✅. | `implement` starts. Bob's agent shows the 004 button when the rules of 004 ask for it. |
| 3 | Look at who claims `review`. | Not the agent that did `implement`. |
| 4 | Post a trigger with `flow:bugfix <issue text>` from `pipe-gitlab` (allowlisted). | The plan and the start message appear. No ✅. |
| 5 | Run `flow:test-run main` with a failing test. | `e2e` is `failed` with `run_failed`. `troubleshoot` starts once. The report and screenshots are in the thread as files. The flow ends. |
| 5 | Use a very short `step_timeout_min` and run `test-run`. | `e2e` is `failed` with `timeout` and a "Retry" button. `troubleshoot` does not start. |
| 6 | Post a trigger with `flow:troubleshoot <alert text>` from an allowlisted alert bot. | `collect`, `diagnose`, `implement`, then the approval button. |
| 7 | Run `flow:review-handoff <MR link>`. | `review`, `implement`, `re-review` (not by the agent of `implement`), then the approval button. |
| 8 | Run `flow:planning add a retry to the importer`. Wait for the first question. Reply as Pavlo. | The same agent continues the same step. `hop` stays the same. |
| 8 | Reply as a person who is not Pavlo and not the owner. | The question stays open. |
| 8 | Wait for the task proposal. | The thread shows `needs_approval`. ✅ ends the flow. No work starts. |
| 9 | Run `flow:brainstorm API versioning`. | `context`, a dialog, then a summary document. |
| 10 | Run `flow:research options for a job queue`. | A research step, then a document. |
| 11 | Write "@coder-pavlo @coder-bob flow:delegate add the field X". | A plan with one `write` step for `coder-bob`. After ✅, the 004 gate applies. An MR link comes back. |
| 12 | Run the schedule that posts `flow:nightly` (allowlisted). | The pipeline starts with no ✅. With `check=deps-check`, step 1 uses the tag `deps-check`. |

## 3. Manual checks that need a real LLM

- Write five free-text requests such as "fix the login bug and test it". The planner should pick `bugfix` for bug requests. Write five requests that match no template. The planner must pick none. Record the result here. (Task T060.)

| Date | Request | Planner choice | OK |
|---|---|---|---|
| | | | |

## 4. Checks on the files

- `flows/` has exactly the ten templates and `tags.yaml`.
- No template names an agent, a plugin, a tool, a URL, or a path.
- No file in `~/.pipe/flows/` is written by a test or by the adapter.
