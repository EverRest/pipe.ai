# Contract: Run of a `write` step

Source: design brief §5.1, §5.4, §6 (flow C), §8, constitution principles IV, VI, XI. Spec FR-010 to FR-016. Extends [../../003-chat-pipelines/contracts/runtime-request.md](../../003-chat-pipelines/contracts/runtime-request.md). Decision record: [../research.md](../research.md) D5 to D8.

## What the core gives

`RunRequest((<capability_id>,), "write", requester_is_owner, target)`. `target` is the optional opaque string of the plan step (`None` when the step has none). The core never reads it. The core names no tool, no path, no repo, no branch, and no provider. `RuntimeInput.task` is `{id: thread_ts, purpose: "step", step: <index>, pipeline: {goal}}` (003). `RuntimeInput` has no new field.

The core reads the result: `text`, `status: done`, and `artifacts` (the MR link). The core does not know how the link was made.

## What the `claude` adapter does (`run_write`)

| # | Action | Failure reason (step `failed`) |
|---|---|---|
| 1 | `pick_target(delegate_repos, target)`, then `resolve_repo`: the path is inside `repo_roots` and has `.git`. | `repo not available` (empty map or bad path), `unknown_target`, `target_required` |
| 2 | Check exposure of the capability again (002 `load_set`). | `capability not available` |
| 3 | `git fetch origin <base_branch>`. | `base not available` |
| 4 | `pick_branch(branch_name(task.id, task.step), existing)`, then `git worktree add <worktree_root>/<run_id> -b <branch> origin/<base_branch>`. | `worktree failed` |
| 5 | `map_request(..., workdir=<worktree>)`, `prepare` (002), `build_cmd` with `cwd=<worktree>`, the child run, and `cleanup`. | the 003 reasons (`timeout`, runtime failure) |
| 6 | `git status --porcelain`. No change fails the step. | `no changes` |
| 7 | Check that `HEAD` is the branch of the step. | `branch changed` |
| 8 | `git add -A`, `git commit` (adapter, not the LLM). | `commit failed` |
| 9 | `check_push_ref(branch, base)`, then `MrPublishPort.publish(...)`. | `push failed`, `no merge request` |
| 10 | In a `finally`: `git worktree remove --force`, `git worktree prune`. The branch stays. | (none) |

The result is `RuntimeOutput(text, "done", artifacts=[<MR link>])`. The reason of each failure is a fixed sentence, scrubbed, at most 200 characters (003). A failure after step 4 still runs step 10.

## Tool mapping (`map_request`, `access: write`)

| Item | Value |
|---|---|
| `tools` | `runtime.claude.write_tools` (default `Read`, `Grep`, `Glob`, `Edit`, `Write`). A bare `Bash` is a config error (DQ8). Same for the owner and for another person. |
| `allowed` | One rule for each tool, for the worktree path only: `Read(//<worktree>/**)`, `Edit(//<worktree>/**)`, and so on. A scoped `Bash(<command>:*)` entry is passed as it is. |
| `--add-dir` | The worktree. Not `repo_roots`. |
| `cwd` | The worktree. |
| `load` | `load_set(caps, exposed, request.capabilities)`. Exposed items only. |
| `disallowed` | `mcp__<server>` for each `owner-only` server, `Skill(<name>)` for each `owner-only` skill, and every entry of `effective_deny_rules(deny_rules)` (001): `Bash(git push:*)` is always there, also when `deny_rules` is `[]`. |
| every `write` run | `--restricted`, `--permission-mode dontAsk`. |
| no `workdir` | `ValueError` (the adapter turns it into `RuntimeFailed`). |

## MR provider port

```python
class MrPublishPort(Protocol):
    def publish(self, workdir: str, branch: str, base: str, title: str) -> str | None: ...
```

- It pushes the branch only: the refspec `refs/heads/<branch>:refs/heads/<branch>`.
- It returns an `https://` MR link, or `None`.
- The first provider (`mr_gitlab.py`) runs `git push -o merge_request.create -o merge_request.target=<base> -o merge_request.title=<title> origin <branch>` as an argument list. It reads the link from the output. The host of the link must equal the host of the `origin` remote.
- The title is the scrubbed goal, at most 100 characters.
- A new provider needs no change in the core or in the `claude` adapter, except the object that the adapter gets at start.

## Rules

1. Target rules (DQ3): an unknown `target` fails with `unknown_target`. A missing `target` with more than one map entry fails with `target_required`. A missing `target` with one map entry uses that entry. An empty map refuses every `write` step. The reason never holds a name or a path.
2. The runtime never pushes. `Bash(git push:*)` is always denied (`effective_deny_rules`), and `Bash` is not in the default tools.
3. The adapter pushes one ref: the branch of the step. `check_push_ref` refuses `main`, `master`, the base branch, and any name outside `pipe/`. The adapter never pushes to `base_branch`. The MR comes from the new branch (DQ4).
4. `main` has no new commit from the agent after any run (SC-004).
5. No worktree remains after a run (SC-010). The start of the adapter removes the leftovers of a killed run (`sweep_worktrees`).
6. The commit message, the MR title, and every posted text pass `scrub`.
