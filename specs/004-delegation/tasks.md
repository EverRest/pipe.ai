---

description: "Task list for Delegation"
---

# Tasks: Delegation

**Input**: Design documents from `/specs/004-delegation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md. Specs 001, 002, and 003 are implemented (their modules, ports, fakes, and tests exist).

**Mentions**: `escape_mentions` and `mention` in this file mean the functions of the injected `Formatter` of the `Transport` (spec 001 contracts/transport.md). The core has no mention syntax.

**Tests**: Tests are required. Constitution principle VII (NON-NEGOTIABLE): every pure-function business rule has a test task BEFORE its implementation task. The test must fail first. Tests use fakes: no real Slack, no real GitLab, no real Claude. One integration test uses the real `git` with a local bare repo in `tmp_path` (no network).

**Organization**: Tasks are grouped by user story. Paths follow the Source Code layout in [plan.md](plan.md). The tasks follow the owner decisions in "Design decisions" of plan.md (DQ1 to DQ9, pass 2) and constitution v1.3.0 principle XI (the core is capability-agnostic). If the owner changes a decision, change the tasks that plan.md lists for that decision.

**Changes to 003 files**: 004 changes code and tests that 003 made. Each such task says "change" and names the 003 task. 003 tests T016, T027, T032, and T072 assert that `write` is refused. The 004 tasks T009, T011, T013, and T020 replace those cases. The IDs T050 and T051 were added after the first numbering. They sit in Phase 3 (US1), in file order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US3, from [spec.md](spec.md)
- Test tasks start with "Write failing test".

## Path Conventions

Single project: `src/pipe/`, `tests/unit/`, `tests/integration/`, `tests/fakes.py` at the repository root (same as 001 to 003).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the files. Check the 001 to 003 baseline.

- [ ] T001 Create the empty new files from the plan: `src/pipe/core/gate.py`, `src/pipe/runtime_claude_delegate.py`, `src/pipe/git_io.py`, `src/pipe/mr_gitlab.py`
- [ ] T002 Run `pytest tests/unit tests/integration` for specs 001 to 003 (003 with its second batch: `core/source.py`, `step_rejected`, `effective_deny_rules` in the claude adapter). All tests must pass before 004 work starts. Do not add a Python dependency (research.md D9). Check that `git --version` works

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config keys, the gate function, ports, fakes, and the changes that let `write` pass the plan, the route, and the run request. Every story needs them.

**CRITICAL**: No user story work starts before this phase is complete.

- [ ] T003 [P] Write failing test for the new config keys in `tests/unit/test_config.py` (data-model.md "Config keys", research.md D4, D11, DQ3, DQ8):
  - `allowlist` default is `[]`. An entry such as `B012ABCDEF` or `U034GHIJKL` is valid for the Slack `id_pattern` (the test passes the pattern from `FakeTransport`, and the Slack pattern in the Slack mapping test). An entry with a wrong form (`pavlo`, `b012`, `""`, a number) is an error that names the entry. 001 accepted any list: change that case.
  - `runtime.claude.write_tools` default is `[Read, Grep, Glob, Edit, Write]`. A bare `Bash` is an error. A scoped entry `Bash(pytest:*)` is valid. An empty string is an error.
  - `runtime.claude.delegate_repos` is a map `{<name>: <absolute path>}` (DQ3). The default is `{}`. A name that does not match `^[A-Za-z0-9._-]{1,64}$` is an error. `~` in a path is expanded. A path that is not absolute after expansion is an error. A path outside every `runtime.claude.repo_roots` entry (after `realpath`) is an error. A path that does not exist is valid (the step fails at run time, not at load). A value that is not a map (a string or a list) is an error. A key with a single path is an unknown key and an error.
  - `runtime.claude.deny_rules` is not tested here. Spec 001 (T004, T005) defines and tests it, with the default `[]` and `effective_deny_rules`. This test only reads them.
  - `runtime.claude.base_branch` default is `main`. `runtime.claude.worktree_root` default is `~/.pipe/worktrees` (`~` expanded).
  - The core never reads the `runtime` section (data-model.md).
- [ ] T004 Implement the validation of `allowlist` and of the four `runtime.claude` keys in `src/pipe/config.py` (T003)
- [ ] T005 [P] Write failing test for `in_allowlist` and `decide_gate` in `tests/unit/test_gate.py` (FR-004, FR-005, FR-009, SC-001, SC-002, SC-012, research.md D1, D4, DQ1, DQ2). Use opaque IDs such as `B1`, `U1`:
  - `in_allowlist` is an exact match. `None`, `""`, and a near match (`b1`, `B1 `) are `False`. An empty list is always `False`.
  - Rule 1: `access` `read` or `approve` gives `allow`, `not_write`, for any other input.
  - Rule 2: `write`, `executor_owner` set, `starter == executor_owner` gives `allow`, `owner_started`, also with an empty allowlist. An empty `executor_owner` with an empty `starter` does not give `owner_started` (fail closed).
  - Rule 3: sender in the allowlist and `starter == sender_owner` gives `allow`, `allowlisted`. The same with `starter` in the allowlist (a user ID, or a `bot_id` of a bot that started the thread).
  - Rule 3 negative: sender in the allowlist, `starter` is a stranger (not `sender_owner`, not in the allowlist) gives `ask`, `not_allowlisted` (the confused-deputy case, DQ2).
  - A `starter` that is a bot ID in the allowlist (an allowlisted trigger bot of spec 005) with the sender in the allowlist gives `allow`, `allowlisted`. A bot ID that is not in the allowlist gives `ask`.
  - Rule 3 negative: `starter` `None` (unknown) gives `ask`, also when the sender is in the allowlist (fail closed, DQ2). An empty or `None` `sender_owner` never matches a `starter`.
  - Sender not in the allowlist gives `ask`, also when `starter` is in the allowlist.
  - The test table covers every row of data-model.md. The function does not change its input and reads no tool, repo, or provider name.
- [ ] T006 Implement `Gate`, `in_allowlist`, and `decide_gate` in `src/pipe/core/gate.py` (T005). The module imports only the standard library
- [ ] T007 [P] Extend `src/pipe/ports.py`: add the Protocols `GitPort` (`run(cwd, args) -> GitResult`) and `MrPublishPort` (`publish(workdir, branch, base, title) -> str | None`), the dataclass `GitResult(code, out, err)`, and the exception `PublishFailed(reason)` (data-model.md "Ports added"). Change no other port
- [ ] T008 [P] Extend `tests/fakes.py` (depends on T007):
  - `FakeGit` records each call (`cwd`, `args`) and returns canned `GitResult` values by argument prefix.
  - `FakeMrPublisher` records each call and returns a canned link, `None`, or raises `PublishFailed`. A variant `LocalPushPublisher` runs the real `git push origin <branch>` against a local remote and returns a canned link (used by T021 and T040 only).
  - A helper `make_write_thread(...)` builds a `ThreadState` and a `FakeTransport` thread with an approved plan that has a `write` step, two cards (sender and receiver, with `owner`), and the `starter`.
  - `FakeTransport.click` already builds the click events (003). Add no method for a bot-to-user lookup (SC-012 of 003 stays).
- [ ] T009 [P] Change the test of `validate_plan` in `tests/unit/test_validate_plan.py` (003 T016; FR-002, research.md D8). Write failing cases:
  - A bot step with `access: write`, a `capability` that is on the card, and a goal is valid. The old error `not supported before spec 004` is gone.
  - A `write` step with no `capability`, or with a capability that is not on the card, is an error (a hidden capability).
  - A `write` bot step counts toward the limit of `hop_limit(effective_source)` (3 for a free plan). A free plan with 3 bot steps (one `write`) and one human step is valid. A free plan with 4 bot steps is an error. The call is `validate_plan(plan, cards, starter, flows)`.
  - A `write` step before an `approve` step is valid. A human step with `access: write` is an error. `access: delete` is an error.
  - The step still has no field `kind` and no field `skill`. A step with one of them is an error.
  - A `write` step with an optional `target` string (for example `app`) is valid. `validate_plan` gives no error for any string `target`, also for a name that no card or map holds (DQ3: the map of the target agent is private). A `target` that is not a string, or has more than 64 characters, is a parse error (`parse_task`).
- [ ] T010 Change `validate_plan` and the `Step` dataclass in `src/pipe/core/pipeline.py` (T009; same file as 003 T004): rule 2 accepts `write` for a bot step, and rule 3 allows `read` or `write` for a bot step (data-model.md "Plan rules changed for write"). `Step` gets the optional field `target: str | None`. `parse_task` accepts it. `validate_plan` has no rule on `target`
- [ ] T011 [P] Change the test of the `BotMessage` branch of `route` in `tests/unit/test_route_bot.py` (003 T027; FR-003, research.md D8). Write failing cases:
  - A valid handoff with `next.access: write` for this agent gives `claim` (the old `ignore(unsupported_access)` is gone for `write`).
  - A handoff with `next.access: approve` still gives `ignore(unsupported_access)`.
  - A `write` handoff with `hop` 4 in a free plan gives `refuse` (`hop_limit` of 003). With a verified template source, `hop` 4 gives `claim` and `hop` 6 gives `refuse`. A `write` handoff from a bot with no card gives `ignore(no_card)`. A `write` handoff that the plan does not assign to this agent gives `ignore(not_assigned)`.
  - The access in `next` must equal the access of the step in the plan. A mismatch gives `ignore(not_assigned)`.
  - The decision for `write` is `claim`. The gate is not in `route` (research.md D2).
- [ ] T012 Change the `BotMessage` branch of `route` in `src/pipe/core/route.py` (T011; same file as 003 T022): accept `write`, keep `approve` unsupported, and check that `next.access` equals the plan access of the step
- [ ] T013 [P] Change the test of `build_run_request` in `tests/unit/test_runrequest.py` (003 T032; FR-013). Write failing cases:
  - A `write` bot step started by the owner: `RunRequest((<capability>,), "write", True, None)`. A `write` step with `target: "app"` gives `RunRequest((<capability>,), "write", <bool>, "app")`. The core passes `target` as it is and does not read it (DQ3). A `read` step gives `target=None`. The same step started by another person: `requester_is_owner` is false. An empty `owner` gives false.
  - `capabilities` holds the one capability of the step. The ID is opaque (`cap-1`).
  - A `write` step no longer raises `ValueError`. An `approve` step still raises `ValueError`.
  - The result has no field with a tool name, a path, a branch, or a flag. The only repo-related field is the opaque `target` string.
- [ ] T014 Change `RunRequest` and `build_run_request` in `src/pipe/core/runrequest.py` (T013; same file as 003 T036): accept `write`, add the optional field `target`
- [ ] T015 [P] Change the test of `render_task` in `tests/unit/test_render.py` (003 T011; contracts/gate.md "Texts"). Write failing cases:
  - The gate request (type 4, `needs_approval`, `write`) gives the text of the contract, with the names from the cards and a real `<@U_OWNER>` mention. Every other mention is escaped.
  - The rejected step gives `failed. Reason: rejected`. The running `write` step gives the text with the word `write`.
  - A token-like string in a goal or reason becomes `[redacted]`. No text holds a path or a URL.
- [ ] T016 Change `render_task` in `src/pipe/core/render.py` (T015; same file as 003 T012): the gate texts
- [ ] T017 [P] Change the import-boundary test in `tests/unit/test_core_boundary.py` (003 T071; FR-018, SC-008, principle XI). Write failing cases:
  - The list of core modules gets `gate.py`. The test first checks that `src/pipe/core/gate.py` exists. The check covers all modules of `src/pipe/core/` (the 003 T071 list: 13 with `gate.py` and `schema.py`).
  - The list of forbidden imports gets `pipe.runtime_claude_delegate`, `pipe.git_io`, and `pipe.mr_gitlab`.
  - The list of forbidden terms gets `worktree`, `git`, `merge`, `push`, and `commit`. The word `branch` is NOT forbidden: spec 003 uses `branch_target`, `bad_branch`, and `branch_step` for the `on_fail` branch (FR-040), which is not a git branch. A term matches a whole word inside an identifier or a string constant (split on `_` and on non-letters), so `digit` and `legit` do not match. The A2A field `skills` and the type `CardSkill` stay allowed.
  - The negative case from 003 stays. Add a second negative case: a temporary module with `import pipe.git_io` makes the checker report an error.
  - Check by hand that the 003 core modules hold none of the new terms. The test must pass for them after T006 (a word such as `merge` in an old text is a finding to fix in that module).

**Checkpoint**: Foundation ready. User stories can start.

---

## Phase 3: User Story 1 - Delegate to an allowlisted sender (Priority: P1) MVP

**Goal**: A `write` step from an allowlisted sender starts without a button. The `claude` adapter works in a worktree on a branch and gives an MR link. `main` is unchanged.

**Independent Test**: Run `pytest tests/unit/test_runtime_claude_delegate.py tests/unit/test_mr_gitlab.py tests/unit/test_runtime_claude_request.py tests/integration/test_delegation_allowlist.py tests/integration/test_delegation_git.py tests/integration/test_plan_flow.py`. Then do the quickstart scenarios "1".

### Tests for User Story 1 (write first, they MUST fail)

- [ ] T018 [P] [US1] Write failing test for the pure helpers in `tests/unit/test_runtime_claude_delegate.py` (FR-010, FR-011, FR-014, research.md D5, D6, data-model.md "Branch and worktree"):
  - `branch_name("1700000000.000100", 1)` gives `pipe/1700000000-000100-s1`.
  - `pick_branch(name, existing)` gives `name` when free, `name-2` when `name` exists, and `name-3` when both exist.
  - `resolve_repo(path, repo_roots)` gives the `realpath` of `path` when it is inside a `repo_roots` entry and holds `.git`. It gives `None` for: a path outside the roots, a symlink that leaves the roots, and a directory with no `.git`. Use `tmp_path`.
  - `check_push_ref(branch, base)` raises for `main`, `master`, the base branch (also `origin/main`), a name that does not start with `pipe/`, an empty name, and a name with a space, `..`, `;`, `$`, or a newline. It passes for `pipe/1700-000100-s1`.
  - `commit_message(goal)` has the prefix `pipe: `, the first line of the goal only, at most 72 characters, and a token-like string becomes `[redacted]`.
  - The functions do not change their input.
- [ ] T019 [P] [US1] Write failing test for the GitLab provider in `tests/unit/test_mr_gitlab.py` (FR-012, research.md D6, DQ4). Use `FakeGit`:
  - `push_cmd(branch, base, title)` is a list of arguments (no shell string): `push -o merge_request.create -o merge_request.target=<base> -o merge_request.title=<title> origin refs/heads/<branch>:refs/heads/<branch>`. A title with a quote, a newline, or `;` stays one argument. The title is cut to 100 characters.
  - `parse_mr_url(output, remote_host)` returns the link from a line such as `remote:   https://gitlab.example.com/group/proj/-/merge_requests/12`. It returns `None` when no link exists, when the host differs from `remote_host`, or when the scheme is not `https`.
  - `publish` calls `check_push_ref` first. For `main` it raises and makes no git call.
  - `publish` reads the host of `origin` with `git remote get-url origin` (https and ssh forms), pushes, and returns the link. A push with a non-zero code raises `PublishFailed("push failed")`. A push with code 0 and no link returns `None`.
  - No error text and no returned value holds a token or a remote URL with a password.
- [ ] T020 [P] [US1] Change the test of `map_request` in `tests/unit/test_runtime_claude_request.py` (003 T072; FR-013, SC-006, research.md D7, DQ8). Write failing cases:
  - `write` with `workdir=<wt>`: `tools` = `write_tools`, the same for `requester_is_owner` true and false. `restricted` is true.
  - `allowed` has one rule for each tool and only for `<wt>`: `Read(//<wt>/**)`, `Edit(//<wt>/**)`, and so on. No rule holds a `repo_roots` path. The add-dir list is `[<wt>]`. The working directory is `<wt>`.
  - A scoped `Bash(pytest:*)` entry in `write_tools` is passed as it is. A bare `Bash` is not possible (config error, T003).
  - `write` with no `workdir` raises `ValueError`. The 003 case "`write` raises `ValueError`" is replaced by this case.
  - `read` keeps the 003 behavior (the write tools are removed). Regression cases from 003 T072 stay.
  - `disallowed` holds every entry of `effective_deny_rules(deny_rules)`: `Bash(git push:*)` is always there, also when `deny_rules` is `[]` (FR-024, SC-014). It also holds `mcp__<server>` for each `owner-only` server, and `Skill(<name>)` for each `owner-only` skill. The load set holds exposed items only.
  - Property: for random capability sets and both values of `requester_is_owner`, no `owner-only` rule is in `allowed`, every `owner-only` rule is in `disallowed`, and every path in `allowed` is inside `<wt>`.
  - The function does not change its input.
- [ ] T021 [P] [US1] Write failing test in `tests/integration/test_delegation_git.py` with the real `git`, a local bare repo, a stub `claude`, and `LocalPushPublisher` (FR-010 to FR-012, FR-016, SC-004, SC-005, SC-010):
  - Build `origin.git` (bare) and a clone under a fake `repo_roots` in `tmp_path`, with one commit on `main`. Set `delegate_repos` to `{"app": <clone>}`. The step has no `target` (one entry gives the default).
  - A `write` run (`RunRequest(("cap-1",), "write", False, None)`, `task = {id, purpose: "step", step: 1, pipeline: {goal}}`) makes a worktree under `worktree_root`, runs the stub in it (the stub writes one file), commits on a branch `pipe/...`, pushes it to `origin.git`, and returns `status: done` with the canned MR link in `artifacts`.
  - After the run: `main` in `origin.git` and in the clone has the same commit as before (SC-004). The branch exists in `origin.git` with one new commit. The worktree directory is gone and `git worktree list` shows only the main one (SC-010).
  - The stub command has `cwd` equal to the worktree, `--add-dir` for the worktree only, `--tools` from `write_tools`, `--restricted`, and `Bash(git push:*)` in `--disallowedTools`.
  - A second run for the same task and step (a "Retry") makes a new branch name with a suffix. The first branch stays.
- [ ] T022 [P] [US1] Write failing test in `tests/integration/test_delegation_allowlist.py` with two adapters, `FakeTransport`, `FakeRuntime`, and `FakeMrPublisher` (FR-003 to FR-005, FR-012, SC-001, SC-005):
  - A plan with step 1 (`read`, agent A) and step 2 (`write`, agent B, owner Bob). Alice started the thread. A is in the allowlist of Bob. After ✅ and step 1, B claims step 2 and runs with no button. The claim goes `claimed`, `running`, `done`. The result message (type 5) holds the MR link in `artifacts`.
  - The runtime of step 2 gets `request = RunRequest((<cap>,), "write", False, None)` (`target` is `None` when the step has none) and `task = {id, purpose: "step", step: 1, pipeline: {goal}}`. It gets no `hop`, `from_agent`, `owner`, or trust data (principle VI).
  - A step 2 that Bob started himself runs with no gate, also when the allowlist is empty (FR-004). The runtime request has `requester_is_owner` true and `access: write`.
  - The sender is in the allowlist and the thread starter is the owner of the sender (Alice owns agent A): no button. The same when the starter is in the allowlist. A stranger as thread starter gives a gate request (case of T034).
  - A `read` step from a sender that is not allowlisted runs with no gate (FR-008, DQ1).
  - The goal, the capability, and the `target` come from the plan, not from `next.payload`.
  - No new file appears under `~/.pipe/` besides the 001 to 003 files and the worktree directory.
- [ ] T050 [P] [US1] Write failing test for `pick_target(delegate_repos, target)` in `tests/unit/test_runtime_claude_target.py` (FR-019, FR-020, SC-011, research.md D5, data-model.md "Target resolution", DQ3). Use plain dicts and opaque names such as `app` and `lib`. It is a test-first pair with T051:
  - Unknown: the map `{app: <p1>, lib: <p2>}` and `target="web"` gives the reason `unknown_target`. A near match (`App`, `app `) is also unknown.
  - Required: the same map and `target=None` gives the reason `target_required`. An empty string `target` counts as missing and gives `target_required`.
  - Single default: the map `{app: <p1>}` and `target=None` gives `<p1>`. The same map and `target="app"` gives `<p1>`. The same map and `target="lib"` gives `unknown_target`.
  - Known: the map with two entries and `target="lib"` gives `<p2>`.
  - Empty: the map `{}` gives the reason `repo not available` (FR-020 case 4), for `target=None` and for `target="app"` (the agent refuses every `write` step).
  - The returned reason holds no name and no path. The function does not change its input and does no file access.
- [ ] T023 [P] [US1] Change the test in `tests/integration/test_plan_flow.py` (003 T020; FR-001, FR-002). Write failing cases:
  - A request that needs a file change gives a valid plan with a `write` step. The type 1 message lists `(write)` in the text.
  - The 003 case "an `access: write` step gives a type 2 message" is replaced: a `write` step with a hidden capability or an unknown agent still gives a type 2 message.
  - The planner call still gets `RunRequest((), "read", False)` and the plan schema. The schema `access` enum has `read`, `write`, and `approve`. Each step has an optional string `target` (at most 64 characters). A plan with a `target` on a `write` step passes `validate_plan`. The prompt holds the rules "use `write` only when the goal changes files" and "set `target` only when the request names a repo, and copy the name as written".
  - With the stub `claude`, the planner command still has `--tools ""` and no `--allowedTools`.

### Implementation for User Story 1

- [ ] T051 [US1] Implement `pick_target` in `src/pipe/runtime_claude_delegate.py` (T050; same file as T024): a pure function that returns the path or a fixed reason string, by the five rules of data-model.md "Target resolution"
- [ ] T024 [US1] Implement the pure helpers (`branch_name`, `pick_branch`, `resolve_repo`, `check_push_ref`, `commit_message`) and `run_write` for the happy path in `src/pipe/runtime_claude_delegate.py` (T018, T021; depends on T007, T025, T027, T051). `run_write` calls `pick_target` (T051) with `request.target` and `delegate_repos`, then `resolve_repo`. `run_write` follows contracts/delegation-run.md steps 1 to 10. It takes `GitPort` and `MrPublishPort` as arguments. It calls `prepare` before the child and `cleanup` and the worktree removal in a `finally`
- [ ] T025 [P] [US1] Implement `GitPort` over `subprocess.run` in `src/pipe/git_io.py` (T021; depends on T007): an argument list, no shell, a timeout, `GIT_TERMINAL_PROMPT=0` so that git never waits for a password, and a result of `(code, out, err)`. The error text passes `scrub`
- [ ] T026 [P] [US1] Implement the GitLab provider in `src/pipe/mr_gitlab.py` (T019; depends on T007, T024 for `check_push_ref`): `push_cmd`, `parse_mr_url`, and `publish` (research.md D6). It uses `GitPort` only
- [ ] T027 [US1] Implement the `write` branch of `map_request(..., workdir=None)` in `src/pipe/runtime_claude_request.py` (the deny list comes from `effective_deny_rules(deny_rules)`, never from `deny_rules` alone), and the `write` path of `run` in `src/pipe/runtime_claude.py` (T020; depends on T004, T014, T024): `run` calls `run_write` when `inp.request.access == "write"`. Add `write` to the `access` enum of `PLAN_SCHEMA` and add the optional string `target` (at most 64 characters) to the step schema. The `read` path and the 001 path stay (regression tests)
- [ ] T028 [US1] Change `claim_step` and `run_step` in `src/pipe/stepper.py` (T022; depends on T006, T012, T014, 003 T039 to T041): after the contest, read the card of the sender and call `decide_gate`. Pass `starter` as the ID of the poster of the parent message (the user ID, or the `bot_id` when a bot posted it, else `None`). Use the access of the step in the plan, not `next.access` from the message. `allow` goes on to `run_step`. For `ask`, call `gate_step` (T037). The `allow` path builds the request with `build_run_request` and posts the result with `artifacts` as in 003
- [ ] T029 [US1] Change the planner prompt in `src/pipe/planner.py` (T023; depends on T027): add the rules "use `write` only when the goal changes files" and "set `target` only when the request names a repo, and copy the name as written"
- [ ] T030 [US1] Wire the new objects in `src/pipe/adapter.py` (T022; depends on T025, T026, T028): make `GitPort` and the GitLab `MrPublishPort` at start, pass them to the `claude` adapter, and pass `owner` and `allowlist` from the config to the stepper

**Checkpoint**: User Story 1 works. A `write` step from an allowlisted sender ends in an MR link.

---

## Phase 4: User Story 2 - Ask the owner when the sender is not allowlisted (Priority: P1)

**Goal**: A `write` step from a sender that is not allowlisted waits for the owner. Accept starts the work. Reject fails the step with `reason: rejected`. Only the owner can click.

**Independent Test**: Run `pytest tests/unit/test_route_gate.py tests/unit/test_thread_status.py tests/unit/test_route_wake.py tests/integration/test_delegation_gate.py`. Then do the quickstart scenarios "2".

### Tests for User Story 2 (write first, they MUST fail)

- [ ] T031 [P] [US2] Write failing test for the new `Click` actions of `route` in `tests/unit/test_route_gate.py` (FR-006, FR-007, SC-009, contracts/gate.md, DQ7):
  - `accept` by the card `owner` of this adapter on a type 4 message by this adapter (`write`, `needs_approval`): `accept`. The same for `reject`: `reject`.
  - The same clicks by the thread starter (who is not the owner): `ignore(not_allowed)`. By another person: `ignore(not_allowed)`. By the owner of the sender agent: `ignore(not_allowed)`.
  - A click on a message of another agent, on a message that is `running`, `done`, or `failed`, on a `read` message, or with an unknown action: `ignore`.
  - A second `accept` on a message that is already `running`: `ignore`. An `accept` after a `reject`: `ignore`.
  - A `retry` click on a type 4 message with `failed` and `reason: rejected`: `ignore`. A `retry` click on a `failed` message with another reason still gives `retry` (003).
  - The thread starter is also the owner (no gate arises, but the click rule still holds): `accept` by that person is allowed.
- [ ] T032 [P] [US2] Change the test in `tests/unit/test_thread_status.py` (003 T033; data-model.md "Step state with a gate"). Write failing cases:
  - `step_status` is `needs_approval` for a step whose latest trusted message is a type 4 with that status.
  - `thread_status` is `needs_approval` when the current step has that state (the 003 value for a plan that waits for ✅ is the same word; the plan case is unchanged).
  - A step that is `failed` with `reason: rejected` gives the thread status `failed`. Step 2 is not startable (`next_step_ready`).
  - A `needs_approval` claim counts as a live claim in `resolve_claim` (003 T044 stays valid).
- [ ] T033 [P] [US2] Change the test of the `Wake` branch in `tests/unit/test_route_wake.py` (003 T048; research.md D3). Write failing cases:
  - An own claim with `needs_approval` whose key is not in flight gives `ignore` (no `interrupt`). The button stays valid.
  - An own claim with `claimed` or `running` gives `interrupt` as in 003.
  - After a `Wake`, an `accept` click still gives `accept`.
- [ ] T034 [P] [US2] Write failing test in `tests/integration/test_delegation_gate.py` with two adapters, `FakeTransport`, `FakeRuntime`, and `FakeMrPublisher` (FR-004 to FR-007, SC-002, SC-003, SC-007, SC-009):
  - The sender is not in the allowlist: the claim goes to `needs_approval`. The message has the buttons `pipe_accept` and `pipe_reject` and a mention of the owner. The runtime is not called. No worktree call happens (`FakeGit` has no call).
  - Accept by the owner: the claim goes to `running`, the buttons go away, the run starts, and the result has the MR link. One click gives one run. Two accept clicks give one run (in-flight key).
  - Reject by the owner: the claim goes to `failed` with `reason: rejected`. The message has no buttons and no "Retry" button. The runtime is not called. The thread status is `failed`.
  - A click by the thread starter (not the owner) on accept or on reject changes nothing and posts nothing.
  - The sender is in the allowlist but the thread starter is a stranger: the gate asks (DQ2). With the stranger in the allowlist: it allows.
  - A bot started the thread and its `bot_id` is in the allowlist, and the sender is in the allowlist: no button (a trigger bot counts as a trusted starter). A bot started the thread and its `bot_id` is not in the allowlist: a button. The poster of the parent message is unknown (`starter` `None`): a button (fail closed, DQ2).
  - Two adapters with one bot: the contest leaves one claim, so one gate request appears.
  - The owner of B is offline: the sender posts `waiting`, `owner offline` after `OWNER_OFFLINE_AFTER_S` (003). A gate request that exists counts as a claim, so no `waiting` message follows.
  - The adapter of B restarts (`Wake`) while the button is shown: the message stays `needs_approval`. Accept after the restart works once.
  - The hop count: a gate adds no `hop`. A `hop` 4 handoff gives `refuse` and no gate request.
  - The "Retry" click on a rejected step does nothing.
  - The core uses `step_rejected` of spec 003 for the rejected state. This test file defines no second rule.

### Implementation for User Story 2

- [ ] T035 [US2] Change the `Click` and `Wake` branches of `route` in `src/pipe/core/route.py` (T031, T033; same file as T012): the actions `accept` and `reject` (owner only), no `retry` for `reason: rejected`, and no `interrupt` for `needs_approval`
- [ ] T036 [US2] Change `step_status` and `thread_status` in `src/pipe/core/pipeline.py` (T032; same file as T010): the state `needs_approval` of a step
- [ ] T037 [US2] Implement `gate_step`, `accept_step`, and `reject_step` in `src/pipe/stepper.py` (T034; depends on T016, T028, T035, T036): `gate_step` updates the own claim to `needs_approval` with the buttons and the owner mention. `accept_step` updates the claim to `running` and queues `run_step` (in-flight key `accept:<channel>:<ts>`). `reject_step` updates the claim to `failed` with `reason: rejected` and no buttons (key `reject:<channel>:<ts>`)
- [ ] T038 [US2] Wire the `block_actions` handler for `pipe_accept` and `pipe_reject` in `src/pipe/adapter.py` (T034; depends on T030, T035, T037): route each click through `route`, then run `accept_step` or `reject_step`. Do not save `last_seen_ts` until the step ends or is rejected

**Checkpoint**: User Stories 1 and 2 work.

---

## Phase 5: User Story 3 - Keep foreign work safe (Priority: P2)

**Goal**: Each failure path ends the step with a reason, leaves `main` unchanged, and removes the worktree. A killed adapter leaves no stale worktree after the next start.

**Independent Test**: Run `pytest tests/unit/test_delegation_sweep.py tests/integration/test_delegation_safety.py`. Then do the quickstart scenarios "3".

### Tests for User Story 3 (write first, they MUST fail)

- [ ] T039 [P] [US3] Write failing test for `sweep_worktrees` in `tests/unit/test_delegation_sweep.py` (FR-016, SC-010, research.md D5). Use `tmp_path` and `FakeGit`:
  - A directory in `worktree_root` that no run uses is removed, and `git worktree prune` is called for the repo.
  - A directory of a run that is in flight is kept.
  - A path outside `worktree_root` is never touched. A symlink in `worktree_root` that points outside is removed as a link, and its target stays.
  - An empty or missing `worktree_root` is not an error.
- [ ] T040 [P] [US3] Write failing test in `tests/integration/test_delegation_safety.py` with the real `git`, a local bare repo, a stub `claude`, and `LocalPushPublisher` (FR-011, FR-013 to FR-016, SC-004, SC-006, SC-010):
  - `delegate_repos` empty, or the path is missing, outside the roots, or not a git repo: the step is `failed` with `reason: repo not available`. No git command runs. No worktree exists.
  - Target cases with two or more map entries (DQ3; the unit cases are in T050): an unknown `target` gives `failed`, `unknown_target`. No `target` gives `failed`, `target_required`. A known `target` makes the worktree in the repo of that entry only. With one entry and no `target`, the run uses that entry. No git command runs and no worktree exists for a refused step. The reason text holds no name and no path.
  - A capability that is not exposed now: `failed`, `capability not available`, no worktree.
  - `git fetch` fails (no remote): `failed`, `base not available`.
  - The branch name exists: the run uses the name with a suffix and the old branch is not changed.
  - The stub changes no file: `failed`, `no changes`. No commit, no push, no MR. The worktree is gone.
  - The stub switches to `main` with `git checkout` (it has `Bash` in this test only): the adapter finds that `HEAD` is not the branch of the step and fails the step with `branch changed`. Nothing is pushed. `main` is unchanged.
  - The publisher returns `None`: `failed`, `no merge request`. The branch is pushed. The worktree is gone.
  - The publisher raises `PublishFailed`: `failed`, `push failed`. The worktree is gone.
  - A timeout (`RuntimeFailed("timeout")`): `failed`, `timeout`, a "Retry" button (003), and the worktree is gone.
  - After every case above, `main` in the clone and in `origin.git` has the same commit as before (SC-004), and `git worktree list` shows the main worktree only (SC-010).
  - A token-like string in the goal does not reach the commit message or the title (`[redacted]`).
  - An `owner-only` capability in the request never loads (SC-006): the stub command has no rule for it and has its rule in `--disallowedTools`.
  - With the config `deny_rules: []`, the stub command still has `Bash(git push:*)` in `--disallowedTools` (FR-024, SC-014).

### Implementation for User Story 3

- [ ] T041 [US3] Implement `sweep_worktrees(worktree_root, in_flight, git)` in `src/pipe/runtime_claude_delegate.py` (T039; same file as T024)
- [ ] T042 [US3] Implement the failure paths of `run_write` in `src/pipe/runtime_claude_delegate.py` (T040; same file as T024): the reasons `repo not available`, `unknown_target`, `target_required`, `capability not available`, `base not available`, `worktree failed`, `no changes`, `branch changed`, `commit failed`, `push failed`, and `no merge request`. Each is a fixed sentence. The worktree removal stays in the `finally`
- [ ] T043 [US3] Call `sweep_worktrees` at start and after each Socket Mode reconnect in `src/pipe/adapter.py` (T039; depends on T041; same file as T030). Errors are logged and never stop the start

**Checkpoint**: All user stories work.

---

## Phase 5A: Tag steps with the gate (spec 003 late binding)

**Goal**: A `write` tag step (`agent: any`) shows the gate for the claim winner only, with the owner and allowlist of the winner.

**Independent Test**: Run `pytest tests/integration/test_delegation_tag.py`.

- [ ] T052 [P] [US2] Write failing test in `tests/integration/test_delegation_tag.py` with three adapters (A sends, B and C are eligible), `FakeTransport`, `FakeRuntime`, and `FakeMrPublisher` (FR-023, SC-013, spec 003 T088):
  - A plan has a `write` tag step (`agent: any`, `capability: tag:<tag>`). B and C both have an exposed capability with the tag and no declared `access`. Both claim. The lowest claim `ts` wins. Only the winner calls `decide_gate`. One gate request at most appears. The loser deletes its claim and shows no button.
  - The winner B has the sender in its allowlist and a trusted starter: no button. The same pipeline with C as winner (C has an empty allowlist): C posts the gate request, and C's owner is mentioned. The gate result follows the owner and the allowlist of the winner.
  - An owner reject by the winner gives `failed`, `reason: rejected`, no "Retry". C does not start the step.
  - A bad `payload` (the capability has an `input_schema`) fails with `invalid_payload` before the gate. No button is posted.
  - A declared capability with `access: read` does not bind to a `write` tag step. If it is the only one with the tag, `validate_plan` rejects the plan (no agent offers the tag with a fitting access).
  - The runtime request of the winner is `RunRequest((<bound id>,), "write", <bool>, <target>)`. The core holds no worktree, git, or MR term.
- [ ] T054 [P] [US2] Write failing test in `tests/integration/test_delegation_tag.py` (same file as T052; FR-025, SC-015, spec 003 FR-046, T114). Two eligible adapters B and C. B wins the claim, B's owner rejects, and the step is `failed`, `rejected`. C never claims, also after C restarts and sees the thread again (catch-up and `Wake`). No "Retry" button exists. The test calls `step_rejected` of spec 003 and defines no second rule
- [ ] T055 [US2] Check that `claim_step` and the catch-up pass of `src/pipe/stepper.py` and `src/pipe/adapter.py` call the 003 `step_rejected` result and post no second claim for a rejected `write` tag step (T054; depends on 003 T115; same files as T053, T028). No new core function
- [ ] T053 [US2] Make `claim_step` use the bound step and the claim winner in `src/pipe/stepper.py` (T052; depends on T028, 003 T083, 003 T089; same file as T028 and T037): after the contest and the payload check, call `decide_gate` with the owner and the allowlist of this adapter. The `access` comes from the plan step. A lost claim never reaches the gate

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T044 Run `pytest tests/unit/test_core_boundary.py tests/unit/test_core_purity.py` (SC-008; 003 T064 and T071 cover `gate.py` after T001). `gate.py` must hold no I/O import and no forbidden term. Fix the finding in the module, not in the test
- [ ] T045 Check assumptions A2 and A3 on a real `claude` and a real `git` (research.md "Cannot verify"): the rule syntax `Edit(//<path>/**)` and `Write(//<path>/**)`; `--add-dir` for the worktree; a file outside the worktree is refused; `git push` is denied; the worktree directory is gone after a run, a failure, and a timeout. Fix `src/pipe/runtime_claude_request.py` if the syntax differs
- [ ] T046 Check assumptions A1, A5, and A6 on a real GitLab project (quickstart section 3): the push options create the MR; the output holds the MR link in the form that `parse_mr_url` reads; `main` is a protected branch; the push needs no password. Fix `src/pipe/mr_gitlab.py` if the output differs
- [ ] T047 [P] Check that no file under `src/`, `tests/`, and `~/.pipe/` holds a plain token, and that the sample config shows an `allowlist` with `sender_id` values only (Slack IDs) (constitution; research.md D4). Check that the commit message, the MR title, and each posted reason pass `scrub`
- [ ] T048 Run the manual scenarios of `quickstart.md` section 2 on a real Slack workspace with two adapters of two owners and a real GitLab project. Measure the clicks for SC-007. Read one finished thread alone and write down where the MR link is
- [ ] T049 Run `pytest tests/unit tests/integration` and fix failures (quickstart section 1)

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependency.
- Foundational (Phase 2): needs Phase 1. It blocks all user stories.
- US1 (Phase 3): needs Phase 2. T024 needs T025, T027, and T051. T026 needs T024 for `check_push_ref`. T027 needs T004, T014, and T024. T024, T025, and T027 are one block: write their tests (T018 to T021) first, then implement in the order T025, T024, T027, T026.
- US2 (Phase 4): needs Phase 3 (T028). T037 needs T016, T028, T035, and T036.
- US3 (Phase 5): needs Phase 3 (T024). It does not need Phase 4 for its tests.
- Polish (Phase 6): needs all stories.

### Within Each User Story

- Test tasks come first and MUST fail before the implementation task.
- Pure functions in `src/pipe/core/` before the I/O code that calls them.
- Tasks that edit the same file are not marked [P]: `pipeline.py` (T010, T036), `route.py` (T012, T035), `runtime_claude_delegate.py` (T024, T041, T042), `stepper.py` (T028, T037), `adapter.py` (T030, T038, T043), `runtime_claude.py` and `runtime_claude_request.py` (T027), `test_runtime_claude_request.py` (T020).
- Test-first pairs: T052 before T053. T003 before T004. T005 before T006. T009 before T010. T011 before T012. T013 before T014. T015 before T016. T017 runs with every core task and must pass after T006. T054 before T055. T018 and T021 before T024 and T025. T019 before T026. T020 before T027. T050 before T051. T051 before T024. T022 before T028 and T030. T023 before T029. T031 and T033 before T035. T032 before T036. T034 before T037 and T038. T039 before T041 and T043. T040 before T042.
- T017 changes a 003 test (T071). It needs `gate.py` to exist (T001) and fails until then.

### Parallel Opportunities

- Phase 2: T003, T005, T007, T009, T011, T013, T015, T017 together. T008 after T007.
- US1 tests T018 to T023 and T050 together. T025 beside T024 only after T018 and T021 are written. T026 after T024.
- US2 tests T031 to T034 together.
- US3 tests T039 and T040 together. US3 tests can run beside US2 with another developer after T024.

---

## Parallel Example: User Story 1

```text
# Launch all tests together:
Task: "Write failing test for the pure helpers in tests/unit/test_runtime_claude_delegate.py"
Task: "Write failing test for the GitLab provider in tests/unit/test_mr_gitlab.py"
Task: "Change the test of map_request in tests/unit/test_runtime_claude_request.py"
Task: "Write failing test in tests/integration/test_delegation_git.py (real git, local bare repo)"
Task: "Write failing test in tests/integration/test_delegation_allowlist.py"

# Then the implementation in order:
Task: "Implement GitPort in src/pipe/git_io.py"
Task: "Implement the pure helpers and run_write in src/pipe/runtime_claude_delegate.py"
Task: "Implement map_request write and the run path in src/pipe/runtime_claude_request.py and src/pipe/runtime_claude.py"
Task: "Implement the GitLab provider in src/pipe/mr_gitlab.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1): an allowlisted `write` step ends in an MR link. Stop and validate: tests pass, then quickstart scenarios "1".

### Incremental Delivery

1. Add US2 (the owner gate). Validate. This gives the full M3 acceptance of the design brief.
2. Add US3 (failure paths, sweep). Validate with the safety test.
3. Polish: manual checks on real `claude`, real `git`, real GitLab, and real Slack.

### Traceability

- FR-001: T009, T010, T022, T023. FR-002: T009, T010, T023, T029. FR-003: T011, T012, T022. FR-004: T005, T006, T022, T028, T034. FR-005: T005, T006, T028, T034, T037. FR-006: T031, T034, T035, T038. FR-007: T031, T034, T035, T037. FR-008: T005, T006, T022. FR-009: T003, T004, T005, T006. FR-010: T018, T021, T024. FR-011: T018, T019, T021, T024, T026, T040. FR-012: T019, T021, T022, T026. FR-013: T013, T014, T020, T027, T040. FR-014: T003, T018, T024, T040, T042. FR-015: T040, T042. FR-019: T009, T010, T013, T014, T023, T029. FR-020: T003, T050, T051, T024, T040, T042. FR-021: T031, T037 (no timer task, DQ5). FR-023: T052, T053. FR-024: T020, T027, T040. FR-025: T052, T054, T055. FR-022: no task (003 D8: a runtime `status: delegate` fails the step). FR-016: T021, T039, T040, T041, T043. FR-017: T022, T034 (reuse of 003; hop, claim, timeout, `Wake`), T040. FR-018: T017, T044.
- SC-001: T005, T022. SC-002: T005, T034. SC-003: T031, T034. SC-004: T021, T040. SC-005: T021, T022. SC-006: T020, T040. SC-007: T034, T048. SC-008: T017, T044. SC-009: T031, T034. SC-010: T021, T039, T040. SC-011: T050, T040. SC-012: T005, T034. SC-013: T052. SC-014: T020, T040. SC-015: T054, T055.
- Design brief §9 M3 acceptance: an agent in the allowlist starts work without a button (T022). An agent not in the allowlist gets a button, and reject gives `failed` with `reason: rejected` (T034). The result is an MR from a separate branch and `main` is never changed (T021, T040).
- Design decisions: DQ1 (T005, T006; no gate for `read`), DQ2 (T005, T006, T028, T034), DQ3 (T003, T004, T009, T010, T013, T014, T018, T023, T024, T029, T040, T042, T050, T051; the empty map gives `repo not available`; the planner does not see repo names), DQ9 (T052, T053, T054, T055), DQ4 (T019, T026, T046), DQ5 (no task: a pending button has no expiry), DQ6 (no task: a runtime `status: delegate` fails the step as in 003 D8; the brief marks it reserved), DQ7 (T031, T037), DQ8 (T003, T004, T020, T027).
- Reuse of 003: claim and contest, `build_run_request`, buttons, failure path, offline timer, `Wake`, and metrics (no 004 task for metrics: `compute_metrics` counts an MR link in `artifacts`).

---

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Verify that each test fails before you write the implementation.
- Do not commit from these tasks without an explicit owner request.
- If the owner changes a design decision, change the tasks listed for that decision in the Traceability section.
- `runtime.claude.deny_rules` and `effective_deny_rules` are defined by spec 001. No 004 task defines them again. T020, T027, and T040 call `effective_deny_rules`.
