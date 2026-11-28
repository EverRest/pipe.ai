# Install and configure

## Requirements and installation

- macOS. The adapter uses the `security` and `launchctl` commands.
- Python 3.15 or later (`requires-python = ">=3.15"`).
- Runtime dependencies: `slack_bolt`, `pyyaml`. Test dependency: `pytest`.
- `git` and the `claude` CLI on `PATH`.
- For lint: `ruff` on `PATH`. For the hook: `pre-commit` on `PATH`.

```sh
python3.15 -m venv .venv
.venv/bin/pip install -e ".[test]"
mkdir -p -m 700 ~/.pipe
```

Use the editable install (`-e`). The adapter finds `flows/` relative to the source tree.


## Configuration example

File: `~/.pipe/config.yaml`. The variable `PIPE_HOME` changes the directory.

```yaml
agent_name: <AGENT_NAME>              # required
slack_tokens: keychain:<SERVICE>      # required
owner: <OWNER_USER_ID>                # Slack user ID. Empty: no sender gets tools
description: Agent for <PROJECT>      # at most 200 characters
# model: <MODEL_ID>
# max_budget_usd: 1.0
step_timeout_min: 30

status_channel: pipe-status
work_channel: pipe-work
agents_channel: pipe-agents

exposed: []                           # capability IDs that other people can use
tags: {}                              # capability ID -> list of tags
capabilities: []                      # declared exec or http entries
library_marketplaces: []
allowlist: []                         # Slack bot or user IDs

runtime:
  claude:
    owner_tools: [Read, Grep, Glob]
    repo_roots: [~/code]
    deny_rules: []                    # added to the default deny rules
    write_tools: [Read, Grep, Glob, Edit, Write]
    delegate_repos: {}                # name: absolute path inside repo_roots
    base_branch: main
    worktree_root: ~/.pipe/worktrees

# Optional. Used by `pipe metrics` only.
# mr_state:
#   gitlab:
#     url: https://<GITLAB_HOST>
#     token: keychain:<GITLAB_SERVICE>
```

Rules that [config.py](../../src/pipe/config.py) applies:

- A value that starts with `xox` or `xapp` is an error.
- `owner_tools` and `repo_roots` are not allowed at the top level.
- A broad `Bash` rule is not allowed in `owner_tools`. A `Bash` rule is not allowed in `write_tools`.
- With empty `delegate_repos`, each `write` step fails with `repo not available`.

## Key reference

The source is [config.py](../../src/pipe/config.py).

### Top-level keys

| Key | Type | Default |
|---|---|---|
| `agent_name` | text | required |
| `slack_tokens` | `keychain:<service>` | required |
| `owner` | text (Slack user ID) | empty |
| `description` | text, at most 200 characters | `Claude Code agent <agent_name>` |
| `model` | model ID | not set |
| `max_budget_usd` | number more than 0 | not set |
| `step_timeout_min` | integer, 1 or more | `30` |
| `status_channel` | text | `pipe-status` |
| `work_channel` | text | `pipe-work` |
| `agents_channel` | text | `pipe-agents` |
| `exposed` | list of capability IDs | `[]` |
| `tags` | map: capability ID to a list of tags | `{}` |
| `capabilities` | list of declared entries | `[]` |
| `library_marketplaces` | list of names | `[]` |
| `allowlist` | list of Slack IDs (`B`, `U`, `W`, or `A`) | `[]` |
| `mr_state` | map with `gitlab` | not set |
| `mr_state.gitlab.url` | `https` URL | required in `mr_state.gitlab` |
| `mr_state.gitlab.token` | `keychain:<service>` | required in `mr_state.gitlab` |

### `runtime.claude` keys

| Key | Type | Default |
|---|---|---|
| `owner_tools` | list of tool rules | `[Read, Grep, Glob]` |
| `repo_roots` | list of absolute or `~` paths | `[~/code]` |
| `deny_rules` | list of tool rules | `[]` (the default deny rules always apply) |
| `write_tools` | list, no `Bash` rule | `[Read, Grep, Glob, Edit, Write]` |
| `delegate_repos` | map: name to absolute path inside `repo_roots` | `{}` |
| `base_branch` | branch name | `main` |
| `worktree_root` | absolute or `~` path | `~/.pipe/worktrees` |

### Declared capability keys

| Key | Runtime | Rule | Default |
|---|---|---|---|
| `id` | both | `a-z0-9._-`, at most 64 characters | required |
| `runtime` | both | `exec` or `http` | required |
| `name` | both | 1 to 80 characters | required |
| `description` | both | at most 200 characters | required |
| `access` | both | `read` | required |
| `tags` | both | at most 8 tags | `[]` |
| `timeout_s` | both | 1 to 3600 | `step_timeout_min` x 60 |
| `input_schema` | both | required for an exposed `exec` | not set |
| `output_schema` | both | schema | not set |
| `command` | `exec` | list, first item is an absolute path | required |
| `env_allow` | `exec` | list of variable names | `[]` |
| `url` | `http` | `https`, or `http` for `localhost` and `127.0.0.1` | required |
| `token` | `http` | `keychain:<service>` | not set |

An unknown key in a declared entry is an error.

### Keys that have no effect

[docs/reference.md](../reference.md) lists `dialog_timeout_h`, `flows_dir`, `runtime.name`, and `mr_state.provider`.
`config.py` does not read them. The dialog timeout is always 24 hours.

## Keychain

Slack tokens use the service in `slack_tokens`, with the accounts `bot` and `app`.
A `http` capability token and the GitLab token use their own service, with the account `token`.

```sh
security add-generic-password -U -s <SERVICE> -a bot -w <BOT_TOKEN>
security add-generic-password -U -s <SERVICE> -a app -w <APP_TOKEN>
security add-generic-password -U -s <OTHER_SERVICE> -a token -w <TOKEN>
```

A command line can stay in the shell history. Remove it, or type the command in a shell that does not save history.
