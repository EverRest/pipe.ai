# Data Model: Delegation

All core entities are frozen dataclasses in `src/pipe/core/`. The gate state is not stored in a file. It lives in the thread messages (`pipe.task.v1` metadata). No database. This file adds to [../003-chat-pipelines/data-model.md](../003-chat-pipelines/data-model.md). It does not repeat it.

## Config keys added or changed by 004
File: `~/.pipe/config.yaml`. The core reads only `owner` and `allowlist` (the adapter passes them to `decide_gate`). The four `runtime.claude` keys are read by the `claude` adapter only.

| Key | Type | Rule |
|---|---|---|
| `allowlist` | list[str] | Default `[]`. Each entry is a `sender_id`: a non-empty string. The id pattern comes from the transport (`Transport.id_pattern`; Slack: `^[BUW][A-Z0-9]{2,}$`, a bot ID `B...` or a user ID `U...`, `W...`). An entry that does not match is an error. 001 accepted the key and ignored it. 004 validates and uses it. Spec 005 uses the same list for trigger bots. |
| `runtime.claude.write_tools` | list[str] | Default `[Read, Grep, Glob, Edit, Write]`. Tools of a `write` run. An entry `Bash` with no scope is an error. A scoped entry `Bash(<command>:*)` is allowed (DQ8). Each entry is a non-empty string. |
| `runtime.claude.delegate_repos` | map[str, str] | Default `{}`. Maps a target name to an absolute path (`~` expanded). A name matches `^[A-Za-z0-9._-]{1,64}$`. Each path must be absolute and inside one of `runtime.claude.repo_roots` after `realpath`, else the config load fails. A path that does not exist is not a load error (the step fails at run time). Rules for a step: see "Target resolution" below (DQ3). A single-path key does not exist. |
| `runtime.claude.base_branch` | str | Default `main`. The branch that a worktree starts from and that an MR targets. |
| `runtime.claude.worktree_root` | str | Default `~/.pipe/worktrees`. One directory for each run is made inside it. |

`runtime.claude.deny_rules` is defined by spec 001 (default `[]`, always joined with `Bash(git push:*)` by `effective_deny_rules(deny_rules)` in the `claude` adapter). 004 calls `effective_deny_rules` in `map_request` and does not define it again.

`owner` (001) is the id of the owner in the transport (Slack: a user ID). A `write` step from another person needs it. Without `owner`, `decide_gate` never gives `owner_started` (fail closed).

Constants in code (not config): `MAX_TITLE_CHARS = 100`, `BRANCH_PREFIX = "pipe/"` (in the `claude` adapter, not in the core).

## Gate (core)
File: `src/pipe/core/gate.py`. Pure. Names no tool, no repo, and no provider.

```python
@dataclass(frozen=True)
class Gate:
    action: Literal["allow", "ask"]
    reason: Literal["not_write", "owner_started", "allowlisted", "not_allowlisted"]

def in_allowlist(allowlist: Sequence[str], subject: str | None) -> bool: ...
def decide_gate(access, starter, executor_owner, sender, sender_owner, allowlist) -> Gate: ...
```

| Argument | Meaning |
|---|---|
| `access` | `read`, `write`, or `approve` (the access of the step). |
| `starter` | `sender_id` of the poster of the parent message: a person id, or a bot id when a bot posted it. `None` means unknown (fail closed). |
| `executor_owner` | `owner` of the adapter that runs the step. May be empty. |
| `sender` | `by` of the handoff message: the id of the sender bot (its `sender_id`). |
| `sender_owner` | Card `owner` of the sender. May be `None`. |
| `allowlist` | The config list. |

Decision table (first match wins). The table is the contract of the function ([contracts/gate.md](contracts/gate.md)).

| # | Condition | Result |
|---|---|---|
| 1 | `access != "write"` | `allow`, `not_write` |
| 2 | `executor_owner` not empty and `starter == executor_owner` | `allow`, `owner_started` |
| 3 | `in_allowlist(sender)` and `starter` is not `None` and (`starter == sender_owner` (not empty) or `in_allowlist(starter)`) | `allow`, `allowlisted` |
| 4 | else | `ask`, `not_allowlisted` |

`in_allowlist` is an exact string match. `None` and the empty string never match. The functions do not change their input.

`allow` through rule 3 needs both: the sender in the allowlist, and a trusted starter (DQ2). All other cases give `ask`.

## Tag steps
For a `write` tag step (spec 003 LB2), `executor_owner` and `allowlist` are those of the agent that won the claim. The gate runs after the contest and after the payload check. An agent that lost the claim runs no gate. The function `decide_gate` does not change.

## Step state with a gate (message type 4)
The claim message of a `write` step has these states. The first four are from 003.

| From | To | Cause | Buttons |
|---|---|---|---|
| (new) | `claimed` | The claim at receipt (003). | none |
| `claimed` | `running` | `decide_gate` gave `allow`. | none |
| `claimed` | `needs_approval` | `decide_gate` gave `ask`. The text mentions the owner. | `pipe_accept`, `pipe_reject` |
| `needs_approval` | `running` | The owner clicked Accept. | none |
| `needs_approval` | `failed`, `reason: rejected` | The owner clicked Reject. | none (no "Retry") |
| `running` | `done`, `failed` | As in 003. | `pipe_retry` on `failed` (not for `rejected`) |

`step_status` returns `needs_approval` for a step in the state `needs_approval`. `thread_status` returns `needs_approval` when the current step has that state. A rejected step gives the thread status `failed`. A claim with `needs_approval` counts as a claim for `resolve_claim` and for the owner-offline timer (003): it is a live claim.

## Click events (input of `route`)
`Click.action` gets two values: `accept` and `reject` (003 had `approve` and `retry`). Rules ([contracts/gate.md](contracts/gate.md)):

| Action | Message | Who may click | Decision |
|---|---|---|---|
| `accept` | type 4, by this adapter, `access: write`, `status: needs_approval` | the card `owner` of this adapter | `accept` |
| `reject` | same | same | `reject` |
| `accept` or `reject` | any other message, or a click by another person (the thread starter too) | | `ignore(not_allowed)` or `ignore` |
| `retry` | type 4 with `failed` and `reason: rejected` | | `ignore` |

## Plan rules changed for `write`
003 `validate_plan` rule 2 changes. The rest stays.

2. Each `access` is `read`, `write`, or `approve`. Any other value is an error.
3. A bot agent step needs `access: read` or `access: write` and a `capability`. A `human:<user_id>` step needs `access: approve` and no `capability`.

`write` has no extra plan rule. The step may have an optional `target`: a string of at most 64 characters, an opaque name. `validate_plan` has no rule on `target`. It never reads the content and never compares it with a card, because the map `delegate_repos` of the target agent is private (DQ3). 003 `Step` gets the optional field `target: str | None` and `parse_task` accepts it. The count limit (`hop_limit(effective_source)` bot steps: 3 for a free plan) and the card checks apply as for `read`.

## RunRequest (changed)
003 `build_run_request(step, starter, owner)`: a bot step with `access: write` gives `RunRequest((step.capability,), "write", requester_is_owner, step.target)`. It no longer raises `ValueError` for `write`. `approve` still raises. The `RunRequest` dataclass gets one optional field `target: str | None = None` (default `None`, set only for a `write` step). The core never reads `target`. It holds no path.

## Ports added (`src/pipe/ports.py`)

```python
class GitPort(Protocol):   # the `claude` adapter uses it; the core never does
    def run(self, cwd: str | None, args: Sequence[str]) -> GitResult: ...   # args = git arguments, no shell

class MrPublishPort(Protocol):   # replaceable MR provider (first: GitLab)
    def publish(self, workdir: str, branch: str, base: str, title: str) -> str | None: ...
```

`GitResult` is `(code: int, out: str, err: str)`. `publish` pushes the branch (and only that branch) and returns the MR link, or `None` when no link exists. It raises `PublishFailed(reason)` on a push error.

## Branch and worktree (the `claude` adapter)
| Name | Rule |
|---|---|
| `branch_name(task_id, step)` | `pipe/<task_id with "." replaced by "-">-s<step>`. Example: `pipe/1700000000-000100-s1`. |
| `pick_branch(name, existing)` | `name` when it is not in `existing`. Else `name-2`, `name-3`, and so on. |
| `pick_target(delegate_repos, target)` | Pure. Returns the path of one map entry or a reason. Rules: see "Target resolution". |
| `resolve_repo(path, repo_roots)` | The `realpath` of `path` when it is inside a `repo_roots` entry and has `.git`. Else `None`. |
| `check_push_ref(branch, base)` | Raises when `branch` does not start with `pipe/`, equals `base`, `main`, or `master`, or has a character outside `[A-Za-z0-9._/-]`. |
| `commit_message(goal)` | The scrubbed goal, first line only, at most 72 characters, with the prefix `pipe: `. |
| worktree path | `<worktree_root>/<run_id>`. `run_id` is a random hex string. |

## Target resolution (the `claude` adapter, DQ3)
`pick_target(delegate_repos, target)` rules, first match wins:

| # | Condition | Result |
|---|---|---|
| 1 | The map is empty | `failed`, `repo not available` (the agent refuses every `write` step) |
| 2 | `target` is set and is not a key of the map | `failed`, `unknown_target` |
| 3 | `target` is set and is a key | the path of that entry |
| 4 | `target` is not set and the map has exactly one entry | the path of that entry |
| 5 | `target` is not set and the map has more than one entry | `failed`, `target_required` |

Then `resolve_repo(path, repo_roots)` checks the path (inside `repo_roots`, has `.git`). A failure gives `repo not available`. The reason text never holds the name or the path. The match of a name is exact and case-sensitive. The core sees only the reason string.

## Metrics
No change. `compute_metrics` (003) already counts a step whose `artifacts` holds a merged MR link and whose agent owner is not the thread starter. A delegation of 004 is such a step.
