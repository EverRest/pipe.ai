# Quickstart: Validate Delegation

Use this guide after implementation. It proves the three user stories. It holds no implementation code. Specs 001 to 003 must be installed and working (`pipe doctor` passes, the cards are in `#pipe-agents`, a chat pipeline runs).

## Prerequisites

- Two owners with two adapters: `coder-pavlo` (owner Pavlo) and `coder-bob` (owner Bob). Each has a card in `#pipe-agents`. `coder-bob` exposes at least one capability (002).
- A GitLab project that Bob has checked out under his `runtime.claude.repo_roots`. The `main` branch is protected. Push options are on (GitLab 11.10 or newer). Bob's git login needs no password prompt.
- Config of Bob (`~/.pipe/config.yaml`):
  - `owner`: his Slack user ID.
  - `allowlist`: `[]` at first. Later the bot ID of `coder-pavlo`.
  - `runtime.claude.delegate_repos`: a map from a name to the absolute path of the checkout, for example `{app: /Users/bob/code/app}`. With one entry, a step needs no `target`. With more than one entry, a step needs `target: <name>`. `runtime.claude.base_branch`: `main`.
  - Keep the defaults of `write_tools` and of `deny_rules` (defined by 001). Set `max_budget_usd` (001): a `read` step from another person has no gate and spends your budget.
- No new Slack scope and no new event. The buttons use the interactivity that 003 turned on.
- A channel `#pipe-work`. Both bots are members.

## 1. Unit and integration tests (no Slack, no LLM)

```text
pytest tests/unit tests/integration
```

Expected: all pass. Covers SC-001 to SC-010 and FR-001 to FR-018 with fakes and one real `git` test. The import-boundary test (SC-008) is part of it.

## 2. Scenarios (real Slack)

| Story | Steps | Expected |
|---|---|---|
| 1 | Put the bot ID of `coder-pavlo` in the allowlist of Bob. Pavlo writes in `#pipe-work`: "@coder-pavlo check the README, then @coder-bob fix the typos in it". Pavlo adds ✅. | Step 1 runs. Step 2 for `coder-bob` shows `claimed`, `running`, `done`. No button appears. |
| 1 | Open the result message of step 2. | An MR link is in the thread. The MR comes from a branch `pipe/...`. `main` has no new commit. |
| 1 | Look at `~/.pipe/worktrees` on the laptop of Bob. | The directory is empty. |
| 1 | Bob writes the same request himself and adds ✅. | Step 2 runs with no gate. It still ends in an MR. |
| 2 | Remove the allowlist entry. Pavlo starts the same pipeline. | The step of `coder-bob` shows `needs_approval` with Accept and Reject. The mention pings Bob. No branch and no worktree exist. |
| 2 | Pavlo (the thread starter) clicks Accept. | Nothing changes. |
| 2 | Bob clicks Accept. | The step runs. An MR link appears. |
| 2 | Start the pipeline again. Bob clicks Reject. | The step is `failed`, `rejected`. No "Retry" button. The thread is `failed`. |
| 2 | Start the pipeline again. Stop and start the adapter of Bob. Bob clicks Accept. | The button still works. The step runs once. |
| 2 | Keep the allowlist entry for the bot, and let a stranger (not the owner of `coder-pavlo`, not in the allowlist) start the pipeline. | The gate asks Bob (DQ2). |
| 2 | Put the stranger in the allowlist of Bob and start the pipeline again. | No button. The step runs. |
| 3 | Run a delegation where the stub or a real run changes no file. | The step is `failed`, `no changes`. No MR. No worktree. |
| 3 | Set a path in `delegate_repos` outside `repo_roots` (the loader refuses). Set `delegate_repos` to `{}`. Run a delegation. | The step is `failed`, `repo not available`. |
| 3 | Put two entries in `delegate_repos`. Run a delegation with no `target`. Then run one with `target: nope`. | The first is `failed`, `target_required`. The second is `failed`, `unknown_target`. No worktree exists. |
| 3 | Put two entries in `delegate_repos`. Run a delegation with a `target` that names one entry. | The MR comes from the repo of that entry. |
| 3 | Set `step_timeout_min: 1` and use a capability that sleeps for 5 minutes. | The step is `failed`, `timeout`, with a "Retry" button. The worktree is gone. |
| 3 | Kill the adapter of Bob during a run. Start it again. | The leftover worktree is removed at start. The step is `failed`, `interrupted` (003). |

## 3. Manual checks with real `claude`, `git`, and GitLab (research.md A1 to A3, A5, A6)

1. Run a delegation. Read the output of the push. Expected: GitLab prints the MR link, and `parse_mr_url` reads it. If not, fix the parser.
2. Check that the MR is open, targets `main`, and has the title of the goal.
3. Ask a step to read `~/.aws/credentials` or a file in another repo. Expected: the call is denied (the path rules cover the worktree only).
4. Ask a step to run `git push`. Expected: the call is denied.
5. In GitLab, try to push `main` from the CLI with the adapter branch name `main`. Expected: the adapter refuses (`check_push_ref`), and the protected branch would also refuse.
6. Check `git worktree list` in the repo of Bob after each run. Expected: only the main worktree.
