# Research: Delegation

All "NEEDS CLARIFICATION" items of the Technical Context are resolved. The owner decisions DQ1 to DQ8 are in "Design decisions" of [plan.md](plan.md). This file follows them. Source: `docs/design-brief.md` §5, §6 (flow C), §8, §9 (M3). No Slack access and no network call was used for this research.

## Checked in the repository (2026-11-26)

- 001 accepts the key `allowlist` and ignores it (001 data-model). 004 validates and uses it.
- 003 refuses `access: write` in four places: `validate_plan` rule 2, `route` rule 2 (`unsupported_access`), `build_run_request` (`ValueError`), and `map_request` (`ValueError`). 004 changes these four places. 003 states that spec 004 defines `write`.
- 003 decision Q6: a step that another person started runs with no gate. 004 adds the gate for `write` only.
- 003 has the pieces that 004 reuses. They are: claim and contest (`claim_step`), `build_run_request`, the in-flight keys, the buttons (`pipe_approve`, `pipe_retry`), the failure path, the offline timer, and `Wake`. `compute_metrics` already counts a merged MR link in `artifacts`.
- 002 FR-017: a repo is listed to the owner only. It is always `owner-only` and never enters the card. So a repo cannot be a capability on a card (DQ3).
- 003 `task.id` and `task.step` are in `RuntimeInput.task`. The `claude` adapter can name the branch from them. The runtime contract needs no new field.
- 001 defines `runtime.claude.deny_rules` (default `[]`, FR-019) and `effective_deny_rules(deny_rules)`, which always joins `Bash(git push:*)`. 003 and 004 use the same function in `map_request`. 004 does not define it again.
- 003 `PLAN_SCHEMA` and the `Step` shape have no `target`. 004 adds the optional string `target` (DQ3). The core carries it and never reads it.

## Decisions

### D1. Gate rule (`decide_gate`, pure, in the core)
- Decision: `decide_gate(access, starter, executor_owner, sender, sender_owner, allowlist) -> Gate` (`allow` or `ask`, with a reason code). Rules in order:
  1. `access` is not `write`: `allow` (reason `not_write`). A `read` step keeps decision Q6 of 003 (DQ1).
  2. `executor_owner` is not empty and `starter == executor_owner`: `allow` (`owner_started`). The owner started the pipeline, so the owner decided.
  3. `sender` is in the allowlist, and `starter` is not `None`, and (`starter == sender_owner` (not empty), or `starter` is in the allowlist): `allow` (`allowlisted`).
  4. Else `ask` (`not_allowlisted`).
- `sender` is the `by` of the handoff message (a `bot_id`). `sender_owner` is the card `owner` of that bot. `starter` is the `sender_id` of the poster of the parent message: a person id, or a bot id when a bot posted it. `None` means unknown, and it never gives `allowlisted` (fail closed). A trigger bot (spec 005) that is in the allowlist counts as a trusted starter. An empty `executor_owner` never gives rule 2 (fail closed).
- Rationale: FR-004, FR-005, brief decision 4. Rule 3 checks the sender and the person behind it. This stops a confused deputy: a stranger names an allowlisted agent in a pipeline, and the allowlisted agent hands a `write` step to B. The person starts the work, so the person must also pass (DQ2).
- The function names no tool, no repo, and no provider. It is agnostic (principle XI).
- Alternatives (rejected by the owner): check the sender only; check the thread starter only.

### D2. Where the gate runs
- Decision: `route` is unchanged for the gate: a valid `write` handoff gives `claim` (003). The stepper runs `claim_step` (claim, contest, 003). After the claim wins, the stepper calls `decide_gate`. `allow` goes on to `run_step`. `ask` updates the own claim message to `status: needs_approval` with the buttons `pipe_accept` and `pipe_reject` and a mention of the owner. No runtime runs. No worktree exists.
- The claim contest runs before the gate. So two adapters of one bot show one button, not two.
- State changes of the claim message (type 4): `claimed` to `needs_approval` (ask), then `running` (accept) or `failed` with `reason: rejected` (reject). With `allow`: `claimed` to `running`, as in 003.
- Rationale: the smallest change to 003. No new message type. `needs_approval` is already in the status enum.

### D3. Accept and reject clicks
- Decision: the click rules sit in `route` (rule 4 of 003), as new actions `accept` and `reject`. The message must be a type 4 message by this adapter, with `access: write` and `status: needs_approval`. The clicker must be the card `owner` of this adapter. The thread starter does not count (FR-006; this is stricter than the 003 approve button). A click on any other message gives `ignore`.
- `accept_step` updates the claim to `running` and queues `run_step`. `reject_step` updates the claim to `failed` with `reason: rejected` and removes the buttons. A rejected step has no "Retry" button. A "Retry" click on it gives `ignore`.
- In-flight keys: `accept:<channel>:<ts>` and `reject:<channel>:<ts>`. A second click, or accept and reject together, gives one effect.
- `Wake` (003 rule 5) does not `interrupt` a claim with `needs_approval`. The button stays valid after a restart.
- Rationale: FR-006, FR-007, SC-003, SC-009.
- Ceiling: Slack does not replay a click while the adapter is down. The button stays on the message. The owner clicks again after the adapter starts.

### D4. Allowlist shape
- Decision: `allowlist` is a list of strings. Each string is a `sender_id`. The config loader checks the pattern of `Transport.id_pattern` (Slack: `^[BUW][A-Z0-9]{2,}$`, a bot ID `B...` or a user ID `U...` or `W...`). The pure function `in_allowlist(allowlist, subject)` is an exact string match. Spec 005 calls `in_allowlist` for a trigger bot (`kind: trigger`). The core does not care which kind of ID it is.
- Rationale: FR-009. One generic list serves delegation and triggers (brief decision 14).

### D5. Worktree and branch (the `claude` adapter only)
- Decision: for a request with `access: write`, `runtime_claude.run` calls `run_write` (`src/pipe/runtime_claude_delegate.py`). Steps:
  1. `pick_target(delegate_repos, target)` (pure, DQ3): an empty map fails with `repo not available`. A `target` that is not a key fails with `unknown_target`. No `target` and one entry gives that entry. No `target` and more than one entry fails with `target_required`. Then `resolve_repo(path, repo_roots)`: the path must be inside one of `runtime.claude.repo_roots` after `realpath`, and must hold `.git`. Else the step fails with `repo not available`. Every failure comes before any git command.
  2. `branch_name(task_id, step)` gives `pipe/<task_id with dots as dashes>-s<step>`. `pick_branch(name, existing)` adds `-2`, `-3`, and so on when the name exists (edge case: the branch exists, or a "Retry").
  3. `git fetch origin <base_branch>`, then `git worktree add <worktree_root>/<run_id> -b <branch> origin/<base_branch>`. `base_branch` default is `main`. A fetch failure fails the step with `reason: base not available`.
  4. `map_request(..., workdir=<worktree>)` and `build_cmd` with `cwd=<worktree>`. The runtime runs there.
  5. After the run: `git status --porcelain`. No change fails the step with `no changes`. The adapter checks that `HEAD` is still the branch of the step (an agent that switched branch fails the step). Then `git add -A` and `git commit` with a message from the scrubbed goal. The adapter makes the commit, not the LLM.
  6. The MR provider publishes the branch (D6). It returns the MR link.
  7. In a `finally`: `git worktree remove --force` and `git worktree prune`. The branch stays (it is pushed).
- At adapter start, `sweep_worktrees` removes the directories in `worktree_root` that no run uses, and runs `git worktree prune` (a killed adapter leaves a worktree).
- Rationale: FR-010, FR-011, FR-014, FR-016, FR-019, FR-020, SC-004, SC-010, SC-011. The adapter code does the git work, so the LLM needs no `git` or `Bash` tool.
- Ceiling: one worktree per run, on the laptop disk. No quota. The `git fetch` needs the network and the git credentials of the owner. The adapter uses the owner credentials for a foreign task, but only after the gate and only for the branch of the step (DQ4).

### D6. MR provider (replaceable; DQ4)
- Decision: the port `MrPublishPort.publish(workdir, branch, base, title) -> str | None` (`src/pipe/ports.py`) pushes the branch and returns the MR link. The first provider is `src/pipe/mr_gitlab.py`. It uses GitLab push options: `git push -o merge_request.create -o merge_request.target=<base> -o merge_request.title=<title> origin <branch>`. It reads the MR link from the output of the push (GitLab prints it). The link must be an `https://` URL on the host of the `origin` remote. The title is the scrubbed goal, cut to 100 characters. The command is a list of arguments (no shell).
- Push guard (pure, `check_push_ref(branch, base)`): the branch must start with `pipe/`, must not equal the base or `main` or `master`, and must hold only the characters `[A-Za-z0-9._/-]`. A violation raises an error before any push. The provider pushes the refspec `refs/heads/<branch>:refs/heads/<branch>` only.
- If the push works and no link appears in the output, the provider returns `None`. The step fails with `no merge request`.
- Rationale: FR-011, FR-012. This needs no API token and no new dependency. The push uses the git credentials that the owner already has.
- Alternatives: the GitLab API with a token (a new secret with `api` scope on the laptop); the `glab` CLI (a new tool). Both are in DQ4.

### D7. Tool policy of a `write` run (`map_request`, the `claude` adapter)
- Decision: `map_request(request, caps, exposed, claude_cfg, workdir=None)` for `access: write`:
  - `workdir` is required. Without it: `ValueError`.
  - `tools` = `runtime.claude.write_tools` (default `[Read, Grep, Glob, Edit, Write]`). The tools do not depend on `requester_is_owner`: a `write` step always works in a worktree (D5).
  - `allowed` = one path rule for each tool, for the worktree only: `Read(//<worktree>/**)`, `Edit(//<worktree>/**)`, and so on. `--add-dir` is the worktree. The paths in `repo_roots` are not in the rules. A `Bash` entry in `write_tools` must have the scoped form `Bash(<command>:*)` and is passed as it is (DQ8). A bare `Bash` is a config error.
  - `load = load_set(caps, exposed, request.capabilities)` (002). Exposed items only. No `owner-only` item loads. `disallowed` holds `mcp__<server>` for each `owner-only` server, `Skill(<name>)` for each `owner-only` skill, and every entry of `effective_deny_rules(deny_rules)` of 001 (`Bash(git push:*)` is always there; 004 does not define the key).
  - `restricted` is `True`. `--permission-mode dontAsk` stays.
- `cwd` of the child is the worktree, not `repo_roots[0]`.
- Rationale: FR-013, SC-006. Brief §8: file access for other people comes only with delegation, in a worktree.

### D8. Plan and route changes for `write`
- `validate_plan` (003 rule 2): `access: write` is valid for a bot step. The step still needs a `capability` (rule 3) and the capability must be on the card (rule 6). The limit of `hop_limit(effective_source)` bot steps stays (rule 1; 3 for a free plan). `PLAN_SCHEMA` gets `write` in the `access` enum and an optional string `target` (at most 64 characters) for each step. The planner prompt says: use `write` only when the goal changes files, and set `target` only when the request names a repo (copy the name as written). `validate_plan` has no rule on `target`: the map of the target agent is private, and only the adapter of that agent can check the name (DQ3). `parse_task` and `Step` accept an optional string `target`. 004 owns this extension of the 003 plan shape; 003 has a short note.
- `route` (003 rule 2): `next.access == write` gives `claim` like `read`. `approve` still gives `ignore(unsupported_access)`.
- `build_run_request`: a `write` bot step gives `RunRequest((cap,), "write", requester_is_owner, target)`, where `target` is the opaque string of the step or `None`. A `read` step gives `target=None`. `approve` still raises `ValueError`.
- `parse_task` already accepts `write` (003 T003).
- Rationale: FR-001, FR-002. The goal and the capability still come from the plan, not from `next.payload`.

### D9. Dependencies
| Dependency | Why |
|---|---|
| `slack_bolt`, `pyyaml` (001) | Socket Mode and config. |
| stdlib `subprocess`, `pathlib`, `re` | git commands, path checks, URL parse. |
| `git` CLI (system tool, not a Python package) | Worktree, commit, push. The owner has it already (repos under `repo_roots`). |
| `pytest` (dev only, 001) | Tests, also with a local bare git repo in `tmp_path`. |

No new Python dependency. No `GitPython`. No GitLab client library. No `glab`.

### D10. Testing
- Pure unit tests first: `decide_gate`, `in_allowlist`, `branch_name`, `pick_branch`, `pick_target`, `resolve_repo`, `check_push_ref`, `parse_mr_url`, `push_cmd`, `map_request` (write), `validate_plan` (write), `route` (write, accept, reject), `step_status` and `thread_status` (gate state), `render_task` (gate texts).
- The git code (`git_io.py`) has one integration test with real `git` against a local bare repo in `tmp_path`. It proves the worktree, the branch, the commit, the push, the unchanged `main`, and the removal of the worktree. It needs no network. A stub `claude` script edits one file. `FakeMrPublisher` pushes the branch to the local remote with the real `git` and returns a canned link. Slack uses `FakeTransport`.
- The first GitLab provider has a unit test with a fake `GitPort` that returns canned push output. No test calls real GitLab.
- The import-boundary test of 003 (T071) gets the new core module and the new terms (T017 of 004).

### D11. Config keys added by 004
`allowlist` (validated now), `runtime.claude.write_tools`, `runtime.claude.delegate_repos`, `runtime.claude.base_branch`, `runtime.claude.worktree_root`. The key `runtime.claude.deny_rules` is not new: 001 defines it. Details: [data-model.md](data-model.md). Only the `claude` adapter reads the four `runtime.claude` keys. The core reads only `allowlist` (through `decide_gate` arguments) and `owner`. No Slack scope is new: the buttons use the interactivity that 003 enabled.

### D12. Tag steps (spec 003 late binding)
- Decision: for a `write` step with `agent: any`, the gate runs for the agent that wins the claim contest, after the payload check. It uses the owner and the allowlist of the winner, so one tag step gives one button at most. `decide_gate` does not change. The access fit rule (spec 003 LB1) keeps a declared `read` capability from binding to a `write` step.
- Ceiling: if the owner of the winner rejects, the step is final (DQ7). Spec 003 `step_rejected` (FR-046) enforces it, also after a restart. The other eligible agents are not asked. A later version may re-post the handoff without the rejecting agent.
- Rationale: the smallest change. The contest already picks one agent. The gate already works per agent.

## Cannot verify on this machine

- A1: that GitLab prints the MR link in the output of `git push -o merge_request.create` as a line `remote: ... https://<host>/<path>/-/merge_requests/<n>`. Push options also need GitLab 11.10 or newer. Check in the manual run (T046). If the output differs, fix `parse_mr_url`.
- A2: the exact rule syntax for `Edit(//<path>/**)` and `Write(//<path>/**)` and the effect of `--add-dir` for a path outside the cwd. 001 checked the `Read`, `Grep`, `Glob` form. Check with a real `claude` run (T045).
- A3: that `git worktree add -b <branch> origin/<base>` works on the git version of the owner laptop, and that `git worktree remove --force` leaves no directory. Covered by the integration test with the real `git` of the test machine.
- A4: the Slack payload of a `block_actions` click for the new action IDs. It is the same shape as the 003 buttons (003 A2).
- A5: that the GitLab project has a protected `main` branch. This is defense in depth. The adapter never pushes `main` (D6), but a protected branch also stops a mistake. Check in the manual run.
- A6: that the git credentials of the owner allow a push of a new branch over the remote URL that `origin` uses, without a prompt. If git asks for a password, the push fails and the step fails with `push failed`.
