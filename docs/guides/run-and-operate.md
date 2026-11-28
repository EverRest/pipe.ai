# Run and operate

Nobody tested these steps with live Slack, `claude`, or `launchctl`.

## Commands

| Command | Action |
|---|---|
| `pipe run` | Start the adapter. |
| `pipe doctor` | Check the `~/.pipe` mode, the config, the two Keychain items, and `owner`. |
| `pipe capabilities` | List the found capabilities and their state. |
| `pipe schedule --install` / `--remove` | Add or remove the launchd job. |
| `pipe status-hook SessionStart\|Stop\|SessionEnd` | Claude Code hook. Reads JSON on stdin. Always exits 0. |
| `pipe metrics [--channel N] [--agents-channel N] [--weeks N] [--since YYYY-MM-DD]` | Counts and times from the work channel. `--agents-channel` does not read the config. |
| `pipe flows` | List the flow templates. |
| `pipe flows show <name>` | Show the steps of one template. |
| `pipe flows validate [name]` | Check the templates. |

Run these as `.venv/bin/pipe ...`, or activate the venv.

## 1. Configure

1. Install the project. See [Install and configure](install-and-config.md).
2. Create the directory: `mkdir -p -m 700 ~/.pipe`.
3. Write `~/.pipe/config.yaml`.
4. Store the tokens. See [Set up Slack](setup-slack.md).
5. Run `.venv/bin/pipe doctor`.

`pipe doctor` checks only these items:

- Other users have no access to `~/.pipe`.
- The config loads.
- The Keychain has the items `bot` and `app`.
- `owner` is not empty.

It does not check Slack, `claude`, git, GitLab, or launchd. The output is `PASS all checks`, or `FAIL ...` lines.

## 2. Run in the foreground

```sh
.venv/bin/pipe run
```

At start, the adapter publishes its card, sends a summary DM to the owner, and reads missed mentions.

## 3. Run under launchd

```sh
.venv/bin/pipe schedule --install
.venv/bin/pipe schedule --remove
```

The install command writes these files:

- `~/.pipe/bin/pipe`: a launcher for `pipe run`.
- `~/Library/LaunchAgents/com.pipe-ai.adapter.plist`: the job. It starts at login and restarts after an exit.

The launcher keeps the venv Python path and the directories of `claude` and `git` from the install time.
Install again after you move one of them.

To restart, run `--remove`, then `--install`.

The launcher passes only `PATH`. Variables of your shell do not reach the adapter.

## 4. Session status hook

Add the hooks to `~/.claude/settings.json` by hand. The adapter does not edit that file.

**Use the venv command.** The launcher `~/.pipe/bin/pipe` ignores arguments and starts a second adapter.

```json
{
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": "<REPO>/.venv/bin/pipe status-hook SessionStart"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "<REPO>/.venv/bin/pipe status-hook Stop"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "<REPO>/.venv/bin/pipe status-hook SessionEnd"}]}]
  }
}
```

Merge this with your current settings. The hook does nothing in a child session of the adapter.

## 5. Logs and state

| Path | Content |
|---|---|
| `~/.pipe/logs/adapter.log` | Adapter log. Under launchd, also stdout and stderr. |
| `~/.pipe/logs/hook.log` | Errors of the status hook. |
| `~/.pipe/state.json`, `~/.pipe/seen.json` | Last seen message, card, handled events. |
| `~/.pipe/status/` | Status message of each session. |
| `~/.pipe/run/` | Files of one run. |
| `~/.pipe/worktrees/` | Worktrees of `write` runs. At start, the adapter removes those older than 24 hours. |

## 6. Metrics

```sh
.venv/bin/pipe metrics --weeks 4
```

It needs a config and the bot token. This also applies to `pipe metrics --help`.
For MR state, set `mr_state` in the config. The token comes from `PIPE_GITLAB_TOKEN`, else from the Keychain account `token`.
The GitLab URL must use `https`.

## 7. Common problems

### Start and setup

| Symptom | Cause | Fix |
|---|---|---|
| `config.yaml not found` | No config file. | Create `~/.pipe/config.yaml`. |
| `FAIL config: ...` | A key is invalid. | Correct the key that the message names. |
| `FAIL directory mode` | Other users can open `~/.pipe`. | Run `chmod 700 ~/.pipe`. |
| `FAIL token`, or `keychain item not found` | A Keychain item is missing. | Add the item for account `bot` or `app`. |
| `FAIL owner` | `owner` is empty. | Set your Slack user ID. |
| `pipe run` stops with `KeyError` and a channel name | The adapter cannot find the channel. | Create the channel, or correct the config name. |
| Log: `card step failed` or `card not posted` | The agents channel, a scope, or `owner` is wrong. A card field with a URL, path, or token also stops it. | Read the log line. Correct the cause. |
| `pipe schedule --install` exits with 1 | `launchctl bootstrap` failed. A loaded job is a possible cause. | Run `--remove`, then `--install`. |
| `pipe schedule` prints `not implemented` | No flag. | Add `--install` or `--remove`. |
| `flows: not installed`, or no flows | The install or `flows/` is incomplete. | Install with `pip install -e .`. |

### Chat and plans

| Message in Slack | Cause | Fix |
|---|---|---|
| `Reason: command not found` | `claude` is not on the `PATH` of the adapter. | Install `claude`. Install the launchd job again. |
| `Reason: timeout` | The run was longer than `step_timeout_min`. | Increase the value. |
| `Reason: exit <N>` | The child process failed. | Read the log. For `exec`, the log holds stderr. |
| `I could not build a plan: ...` | The plan check failed. | Read the errors. Check the cards. |
| `flow <name> not found` | Wrong flow name. | Run `pipe flows`. |
| `needs a second agent mention` | The flow uses `$agent`. | Mention a second agent. |
| `missing tags: ...` | No card offers the tag. | Expose and tag a capability. |

### Steps

| Reason | Cause | Fix |
|---|---|---|
| `capability not available` | No exposed capability fits the step. | Check `exposed` and `tags`. |
| `repo not available` | `delegate_repos` is empty, or the path is not a git repository in `repo_roots`. | Correct the config. |
| `target_required`, `unknown_target` | More than one repository, or a wrong name. | Use a name from `delegate_repos`. |
| `base not available` | `git fetch origin <base_branch>` failed. | Check the remote and `base_branch`. |
| `no changes` | The run changed no file. | Make the goal more exact. |
| `push failed` | git rejected the push. | Check your git credentials. |
| `no merge request` | The push output has no MR link on the origin host. | The remote must support the GitLab push options. |
| `no_claimer` | No agent claimed a tag step in time. | Start an eligible adapter. Click Retry. |
| `owner offline` | The step agent did not claim in 60 seconds. | Start that adapter. |
| `interrupted` | The adapter restarted during a step. | Click Retry. |
| `dialog_timeout` | No answer in 24 hours. | Click Retry. |
| `hop limit exceeded` | The pipeline is too long. | Make a shorter plan. |
| `plan source not verified` | The template files differ between adapters. | Use the same checkout and overrides. |
| `exit 2` on the shipped review wrapper | Known input defect. | See [Known defects](../../README.md#known-defects). |
