# Implementation Plan: Delegation

**Branch**: `004-delegation` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-delegation/spec.md`

## Summary

A delegation is a plan step with `access: write` for an agent of another owner. The plan check (003) accepts the step when the card of the agent lists the capability. The receiving adapter takes the handoff, claims the step, and resolves duplicate claims (003). Then the new pure function `decide_gate` decides: `allow` or `ask`. `allow` needs the sender in the allowlist and a trusted thread starter (DQ2). `allow` starts the work. `ask` updates the claim message to `needs_approval` with the buttons Accept and Reject. Only the owner of the receiving agent can click. Reject gives `status: failed` and `reason: rejected`.

The core stays capability-agnostic. It builds `RunRequest((capability,), "write", requester_is_owner, target)` and reads an MR link in `artifacts`. `target` is an opaque optional string from the plan step. The `claude` runtime adapter does the rest. It resolves `target` with `runtime.claude.delegate_repos`, makes a git worktree and a branch, runs `claude -p` in the worktree with file rules for that worktree only (the deny list is `effective_deny_rules(deny_rules)` of 001, so `Bash(git push:*)` is always denied), commits, and gives the branch to a replaceable MR provider. The first provider is GitLab, over git push options on a new branch. The MR link comes back in `artifacts`. The worktree is removed. The adapter never pushes `main`. The new code is small: one core module (`gate.py`), one `claude` adapter module (`runtime_claude_delegate.py`), a git wrapper (`git_io.py`), and the GitLab provider (`mr_gitlab.py`). The rest changes the 003 modules in a few places. Details: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.15 (same as 001 to 003).

**Primary Dependencies**: `slack_bolt`, `pyyaml` (from 001). Test-only: `pytest`. No new Python dependency. The `git` command-line tool is a system tool that the owner has already (research.md D9).

**Storage**: One new directory: `~/.pipe/worktrees/<run_id>/` (key `runtime.claude.worktree_root`). It holds one worktree during one `write` step. Only the `claude` adapter makes and removes it. No new state file. The thread messages hold the gate state. 001 to 003 files are unchanged.

**Testing**: `pytest`. Pure functions have unit tests first, with no Slack, no git, and no LLM. The list: `decide_gate`, `in_allowlist`, `validate_plan` (write), `route` (write, accept, reject), `step_status` and `thread_status` (gate), `render_task` (gate), `build_run_request` (write, target), `map_request` (write, with `effective_deny_rules`), `branch_name`, `pick_branch`, `pick_target` (unknown, required, single default, empty map), `check_push_ref`, `push_cmd`, and `parse_mr_url`. The import-boundary test of 003 (T071) gets the new core module (task T017). Slack, git, and the MR provider sit behind ports with fakes (`FakeTransport`, `FakeRuntime`, `FakeGit`, `FakeMrPublisher`). One integration test uses the real `git` with a local bare repo in `tmp_path` and a stub `claude`. A manual run with real Slack, real `claude`, and real GitLab is in [quickstart.md](quickstart.md).

**Target Platform**: macOS laptop (same as 001).

**Project Type**: Extension of the 001 to 003 background process (`pipe run`). No new CLI command.

**Performance Goals**: Owner B accepts or rejects in one click (SC-007). A rejected or expired-by-failure step shows its state in the thread at once.

**Constraints**: No server, no database, no web UI. One runtime call at a time per adapter (001). The `claude` adapter keeps `--restricted` on every run. A `write` run reaches only the files of its worktree. No `owner-only` item loads. No plain token in any file. The `hop` limit follows the plan source (3 or less for a free plan, 5 or less for a verified template, 003 and constitution 1.3.0). The core names no worktree, git, branch, MR provider, plugin, skill, MCP server, or runtime tool (principle XI).

**Scale/Scope**: 3 to 6 developers. A few delegations per week.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.3.0.

| Principle | Pre-research | Post-design | Note |
|---|---|---|---|
| I. No Server in the MVP | PASS | PASS | The gate state is in the thread messages. The worktree is a temporary local directory. No database and no service. |
| II. The Owner Controls the Agent | PASS | PASS | This spec adds the owner gate that 003 left out (Q6). The owner holds the allowlist. Only the owner clicks Accept or Reject. A `write` step never runs for a stranger without one of the two. DQ1: `read` steps have no gate. DQ2: the gate checks the sender and the thread starter. |
| III. Discovered Is Not Exposed | PASS | PASS | A `write` step needs a capability that the card lists (exposed only). The `claude` adapter checks exposure again at run time and blocks `owner-only` items in `disallowed`. A repo is not a capability (002 FR-017). The owner names the target repos in the config map `delegate_repos` (DQ3). The names and paths never enter the card. |
| IV. Every Change Goes Through an MR | PASS | PASS | Every `write` step, also an owner-started one, runs in a worktree on a branch and ends in an MR. The runtime has `effective_deny_rules(deny_rules)` of 001 denied (`Bash(git push:*)` is always in the list, also when `deny_rules` is `[]`) and no `Bash` by default. The adapter code pushes only the branch of the step. `check_push_ref` refuses `main`, `master`, and the base branch. The merge by a human is the approval. |
| V. Thread Content Is Untrusted Input | PASS | PASS | The trust checks of 003 stay (cards, `by`, planner). Accept and Reject count only from the owner of the receiving agent, which is stricter than "thread starter or owner". The goal, the capability, and the `target` come from the plan, not from `next.payload`. The `target` is untrusted text: the adapter accepts only a name that is a key of the owner map `delegate_repos`. The thread goes to the runtime as untrusted text. |
| VI. Runtime-Agnostic Contract | PASS | PASS | `RuntimeInput` has no new field. `RunRequest` gets one optional field `target`: an opaque name, no path. The runtime gets `task.id`, `task.step`, the goal, and `request`. It knows no `hop`, no trust data, and no Slack data. The worktree is a detail of the `claude` adapter. See [contracts/delegation-run.md](contracts/delegation-run.md). |
| VII. Business Rules Are Pure Functions | PASS | PASS | `decide_gate`, `in_allowlist`, the route changes, `map_request` (write), `check_push_ref`, `branch_name`, and `parse_mr_url` are pure. Test tasks come before implementation tasks. |
| VIII. Reuse Before Build | PASS | PASS | Reuses the 003 claim, contest, buttons, failure path, offline wait, `Wake`, and metrics. Reuses the 002 load set. Reuses git push options of GitLab instead of an API client. wiz-review is not needed here (spec 005). |
| IX. Small Dependencies | PASS | PASS | No new Python dependency. The `git` tool is a system tool (research.md D9). |
| X. STE for All Written Artifacts | PASS | PASS | All artifacts use STE. |
| XI. Core Is Capability-, Runtime-, and Transport-Agnostic | PASS | PASS | The only new core module is `core/gate.py`. It reads neutral ids only (`sender_id`, `card_owner_id`). It uses opaque IDs. The core builds a `RunRequest` with `access: write` and reads `artifacts`. Worktree, git, deny rules, and MR creation are in `runtime_claude_delegate.py`, `runtime_claude_request.py`, `git_io.py`, and `mr_gitlab.py`. The MR provider is a port (`MrPublishPort`). `test_core_boundary.py` is extended (T017). |

Technology and Security Constraints: tokens in Keychain (PASS: no new token; the push uses the git credentials of the owner, DQ4). Scrub before post (PASS: every posted text, the reason, the commit message, and the MR title pass `scrub`). A foreign task loads only exposed capabilities and no `owner-only` item (PASS: T020, T040). `hop` limit by plan source, 3 or 5 (PASS: 003 `hop_limit`; the gate adds no `hop`). Cards hold no MCP URL, token, or path (PASS: 004 does not change the card). Delegated work runs in a separate git worktree and branch (PASS: T021, T024).

**Result**: PASS. No deviation. No Complexity Tracking row. The eight design decisions are in the next section.

## Design decisions

The owner confirmed these decisions on 2026-11-26. The tasks follow them. Each decision lists the affected tasks.

**DQ1 = (a). `read` steps from other people have no gate.** Only a `write` step from another person goes through the gate. A `read` step has no file tool for another person and loads exposed capabilities only (003 Q5, Q6). Exposure is the limit. Note: the owner should set `max_budget_usd` (001), because a step that another person starts spends the budget of the owner. Affected tasks: T005, T006.

**DQ9 (2026-11-26). Tag steps.** For a `write` tag step (spec 003 late binding), the gate runs after the claim contest, for the winner. It uses the owner and the allowlist of the winner. The loser has no gate. The payload check runs before the gate. A rejected `write` tag step gets no second claimer, also after a restart (`step_rejected`, spec 003 FR-046, N13; FR-025). Affected tasks: T052, T053, T054, T055.

**DQ2 = (b). The gate checks the sender and the thread starter.** The gate starts the work without a click only when both conditions are true: (1) the sender bot is in the allowlist, and (2) the thread starter is the owner of the sender bot or is in the allowlist. In all other cases, the owner gets the accept/reject button. This stops a confused deputy: a stranger names an allowlisted agent in a pipeline and reaches the repo of B through it. The thread starter is the `sender_id` of the poster of the parent message: a person id, or a bot id when a bot posted it (a trigger bot of spec 005 is in the allowlist or not). An unknown starter gives the button (fail closed). A user ID in the allowlist trusts that person for every agent. Affected tasks: T005, T006, T028, T034.

**DQ3 = owner variant. A map of target repos.** The config key `runtime.claude.delegate_repos` is a map `{<name>: <absolute path>}`. Each path must be inside one of the `repo_roots` entries. A plan step can have an optional `target: <name>`. The core carries `target` as an opaque string (in `RunRequest.target`). Only the `claude` adapter resolves it:
- A `target` that is not in the map: `status: failed`, `reason: unknown_target`.
- The map has exactly one entry: `target` is optional and defaults to that entry.
- The map has more than one entry and `target` is missing: `status: failed`, `reason: target_required`.
- The map is empty: the agent refuses every `write` step (`reason: repo not available`).

Repo paths and names never go into the card, so 002 FR-017 stays unchanged. `validate_plan` does not check `target`, because the map of the target agent is private. The planner schema (003 contract `plan-schema.md`) gets the optional string `target`. Spec 004 owns this extension. Affected tasks: T003, T004, T009, T010, T013, T014, T018, T023, T024, T029, T040, T042, T050, T051.

**DQ4 = (a). GitLab push options.** The adapter creates the MR with git push options (`-o merge_request.create` and `-o merge_request.target=<base_branch>`) on a new branch. It never pushes to `base_branch`. It adds no secret and no tool. The adapter reads the MR link from the push output. If the link is missing, the step fails with `no merge request`, and the branch is already pushed (research.md A1). Affected tasks: T019, T026, T046.

**DQ5 = (a). A pending button has no expiry.** The step stays `needs_approval` until the owner clicks. A stale thread is visible, and the requester can start a new thread. Affected tasks: none.

**DQ6 = (a). Only plan steps start a delegation.** A runtime result with `status: delegate` does not start one. The step fails as in 003 D8 (a status other than `done` fails the step). The status `delegate` of the brief §5.1 stays unused. The brief now marks it "reserved, ignored by the core". Affected tasks: none.

**DQ7 = (a). No Retry after a reject.** A rejected step has no "Retry" button. The requester starts a new thread. Affected tasks: T031, T037.

**Pass 2 (2026-11-26, owner-confirmed, constitution 1.3.0).**
- **P2-1. Deny list.** `map_request` builds the deny list with `effective_deny_rules(deny_rules)` of the `claude` adapter (spec 001, 003). The result always holds `Bash(git push:*)`. Tasks: T020, T027 (FR-024, SC-014).
- **P2-2. Starter.** The thread starter can be a bot ID. An allowlisted trigger bot is a trusted starter. An unknown starter gives the button (fail closed). This is DQ2 and is now written in FR-005 and in T005, T034.
- **P2-3. Empty `delegate_repos`.** The step fails with `reason: repo not available`. Tasks: T050, T040.
- **P2-4. `target`.** It travels in `RunRequest.target` (opaque). Tasks: T013, T014.
- **P2-5. Planner and repo names.** The planner does not see repo names (accepted). The request text must carry the name. Task: T023, T029.
- **P2-6. Rejected tag step.** `step_rejected` (003) is the only rule. Tasks: T054, T055.
- **P2-7. Names.** "Owner gate" is the type 4 `needs_approval` of this spec (buttons `pipe_accept`, `pipe_reject`). Type 5 `needs_approval` (`gate: approval`, proposal) is spec 003. A ✅ release posts a NEW type 5 `done`. Type 10 is the dialog question. Type 11 is the branch handoff. This spec changes none of them.

**DQ8 = (a). `write_tools` has no bare `Bash`.** `write_tools` defaults to `[Read, Grep, Glob, Edit, Write]`. A scoped `Bash(<cmd>:*)` entry is allowed. A bare `Bash` entry is a config error. Reason: a `Bash` tool runs with the user rights of the owner and can leave the worktree. The path rules do not confine it. The cost: the agent cannot run tests by default. The MR review and CI check the change. Affected tasks: T003, T004, T020, T027.

## Design questions O1 and O2 (pass 2, decided 2026-11-26)

These points came out of the full analyze. The owner accepted the recommendation for each. They affect only a `write` step.

- **O1. Dialog or proposal in a `write` step.** A runtime result `waiting` with `needs_input` (003 N1) ends `run_write` before a commit. Options: (a) remove the worktree, post the question, and start a new worktree on the resume (no state, simple); (b) keep the worktree during the dialog (state, a leak risk, needs a sweep rule). **Decided: (a).** The resume is the same claim, so the owner gate does not ask again. A `proposal` from a `write` run is treated as `done` without a proposal: the step ends `failed`, `reason: runtime status proposal`.
- **O2. `gate: approval` on a `write` step.** Two gates can apply: the owner gate (type 4) before the run, and the type 5 gate after the run (MR link in the gate message). **Decided: allow it.** The order is fixed: the owner gate first, then the run, then the type 5 gate.

## Project Structure

### Documentation (this feature)

```text
specs/004-delegation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── gate.md
│   └── delegation-run.md
├── checklists/requirements.md
└── tasks.md             # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

New files are marked `+`. Changed 001, 002, or 003 files are marked `~`.

```text
src/pipe/
├── core/                            # PURE functions only. No runtime-specific module
│   ├── gate.py              +       # in_allowlist(allowlist, subject); decide_gate(...) -> Gate(action, reason)
│   ├── pipeline.py          ~       # Step gets an optional target (opaque string); validate_plan(plan, cards, starter, flows) accepts write and does not check target; step_status and thread_status know the gate state (003 `step_rejected` is reused, not redefined)
│   ├── route.py             ~       # write handoff gives claim; Click actions accept and reject; Wake leaves a gate claim alone
│   ├── runrequest.py        ~       # build_run_request accepts a write bot step; RunRequest gets an optional target (opaque)
│   └── render.py            ~       # texts of the gate request and of reject
├── runtime_claude_delegate.py +     # `claude` adapter: pure helpers (branch_name, pick_branch, pick_target, resolve_repo, check_push_ref, commit_message) and run_write
├── runtime_claude_request.py ~      # map_request(..., workdir=None): write branch; deny list = effective_deny_rules(deny_rules) (001)
├── git_io.py                +       # GitPort over subprocess (list args, no shell): fetch, worktree add/remove/prune, status, head, add, commit
├── mr_gitlab.py             +       # first MrPublishPort provider: push_cmd, parse_mr_url, publish (GitLab push options)
├── config.py                ~       # allowlist validation; runtime.claude write_tools, delegate_repos (map name to absolute path), base_branch, worktree_root; deny_rules is defined by 001
├── ports.py                 ~       # GitPort, MrPublishPort
├── runtime_claude.py        ~       # run(inp): access write goes to run_write; PLAN_SCHEMA access enum has write and each step has an optional target
├── planner.py               ~       # prompt rules: use write only when the goal changes files; set target only when the request names a repo, copied as written
├── stepper.py               ~       # gate_step, accept_step, reject_step; claim_step calls decide_gate
├── adapter.py               ~       # block_actions: pipe_accept, pipe_reject; inject GitPort and MrPublishPort; sweep_worktrees at start
└── (cli.py unchanged)

tests/
├── unit/                            # test_gate.py, test_runtime_claude_delegate.py, test_runtime_claude_target.py, test_mr_gitlab.py, test_route_gate.py
│                                    # (+ changes to test_config.py, test_validate_plan.py, test_route_bot.py, test_route_wake.py,
│                                    #   test_runrequest.py, test_runtime_claude_request.py, test_thread_status.py, test_render.py,
│                                    #   test_core_boundary.py)
├── fakes.py                 ~       # FakeGit, FakeMrPublisher
├── integration/                     # test_delegation_allowlist.py, test_delegation_gate.py, test_delegation_git.py, test_delegation_safety.py
│                                    # (+ change to test_plan_flow.py)
└── manual/                          # none new
```

**Structure Decision**: Single project, same layout as 001 to 003. The new rule `decide_gate` sits in `core/` as a pure function. All git, worktree, and MR code sits in the `claude` adapter files and a provider behind a port.

## Complexity Tracking

No constitution deviation. No row.
