# Implementer reference: Slack scopes and config keys

Status: consolidated on 2026-11-26 (pass 2, constitution 1.3.0). This file collects facts from specs 001 to 006. It makes no decision. When this file and a spec differ, the spec wins. Fix this file.

## 1. Slack scopes and settings

### Agent app (one Slack app for each agent adapter)

| Item | Needed by | Source |
|---|---|---|
| Socket Mode on | all | 001 |
| App-level token scope `connections:write` (token `xapp-...`) | Socket Mode | 001 |
| Bot scope `app_mentions:read` | mention events | 001 D5 |
| Bot scope `chat:write` | post and update messages | 001 D5 |
| Bot scope `channels:history` | catch-up, thread read | 001 D5 |
| Bot scope `channels:read` | find channels, `users.conversations` | 001 D5 |
| Bot scope `metadata.message:read` | read `pipe.task.v1` and `pipe.card.v1` metadata | 001 D5 |
| Bot scopes `groups:history`, `groups:read` | only for a private `#pipe-work`, `#pipe-agents`, or `#pipe-status` | 001 D5, 002 D12, 003 |
| Bot scope `files:write` | `Transport.upload_file` (screenshots, reports) | 001 FR-024 |
| Bot scopes `pins:write`, `pins:read` | pin and read the card in `#pipe-agents` | 002 D12 |
| Bot scope `im:write` | open a DM with the owner (notices) | 002 D12 |
| Bot scope `reactions:read` | ✅ release and start | 003 |
| Event `app_mention` | all mentions and handoffs | 001 D5 |
| Event `reaction_added` | ✅ on a plan or a gate | 003 |
| Interactivity on (no request URL in Socket Mode) | buttons: `pipe_approve`, `pipe_retry`, `pipe_accept`, `pipe_reject` | 003, 004, 005 |

Do NOT add `users:read`. The mention of an agent uses `bot_user_id` from its card (003 Q7). Reinstall the app after a scope change.

A dialog answer needs a mention of the agent, so it arrives as `app_mention`. No `message.channels` event is needed (003 U3).

### Trigger bot app (for example `pipe-gitlab`, spec 005)

| Item | Source |
|---|---|
| Bot scope `chat:write` | 005 |
| No event subscription, no Socket Mode | 005 |
| Token in a masked CI variable, for example `SLACK_TRIGGER_TOKEN` | 005 FR-023 |

### Other scopes (not Slack)

| Item | Source |
|---|---|
| GitLab token with scope `read_api`, in the macOS Keychain, for `pipe metrics` only | 003 |
| `git push` of a branch uses the git credentials of the owner. No GitLab token is stored | 004 DQ4 |

## 2. Config keys of `~/.pipe/config.yaml`

The core reads `owner`, `allowlist`, `work_channel`, `step_timeout_min`, and `dialog_timeout_h` only. The `runtime` section is read by the runtime adapter only. A plain token in any key is an error.

### Agent

| Key | Type | Default | Spec |
|---|---|---|---|
| `agent_name` | str | required | 001 |
| `slack_tokens` | str `keychain:<service>` | required | 001 |
| `owner` | str (a Slack user ID) | none (empty: no tools for anyone, gate never gives `owner_started`) | 001 |
| `description` | str | `Claude Code agent <agent_name>` | 002 |
| `model` | str | unset | 001 |
| `max_budget_usd` | number > 0 | unset | 001 |
| `step_timeout_min` | int >= 1 | 30 | 001 |
| `dialog_timeout_h` | int, 1 to 168 | 24 | 003 |

### Channels

| Key | Default | Spec |
|---|---|---|
| `status_channel` | `pipe-status` | 001 |
| `work_channel` | `pipe-work` | 003 |
| `agents_channel` | `pipe-agents` | 002 |

### Capabilities and trust

| Key | Type | Default | Spec |
|---|---|---|---|
| `capabilities` | list of declared capabilities | `[]` | 002 |
| `exposed` | list of capability IDs | `[]` | 002 |
| `library_marketplaces` | list of marketplace names (letters, digits, `-`, `_`; 1 to 64 chars) | `[]` | 007 |
| `tags` | map of capability ID to a list of tags | `{}` | 002 |
| `allowlist` | list of `sender_id` values (bot or user IDs; Slack pattern `^[BUWA][A-Z0-9]{2,}$`) | `[]` | 004, 005 |

Skills, commands, and MCP servers of a plugin from a marketplace in `library_marketplaces` are `owner-only`, even when clean. Only an explicit `exposed` entry exposes them. The marketplace is the part after `@` in the plugin ID `<name>@<marketplace>`.

A declared capability entry has: `id`, `name`, `description`, `tags`, `access` (`read` only), `runtime` (`exec` or `http`), `command` (exec: argv list, absolute first item), `env_allow`, `url` (http: `https`, or `http` for `localhost` and `127.0.0.1`), `token` (`keychain:<service>`), `timeout_s` (1 to 3600), `input_schema`, `output_schema`. An exposed `exec` entry MUST have an `input_schema`. A schema with `additionalProperties: false` must list `context` and `artifacts` (003 FR-037).

### Runtime

| Key | Type | Default | Spec |
|---|---|---|---|
| `runtime.claude.owner_tools` | list | `[Read, Grep, Glob]` | 001 |
| `runtime.claude.repo_roots` | list of paths | `[~/code]` | 001 |
| `runtime.claude.deny_rules` | list | `[]`. `Bash(git push:*)` is always denied (`effective_deny_rules`) | 001 |
| `runtime.claude.write_tools` | list (no bare `Bash`) | `[Read, Grep, Glob, Edit, Write]` | 004 |
| `runtime.claude.delegate_repos` | map of name to absolute path (inside `repo_roots`) | `{}` (every `write` step fails with `repo not available`) | 004 |
| `runtime.claude.base_branch` | str | `main` | 004 |
| `runtime.claude.worktree_root` | str | `~/.pipe/worktrees` | 004 |

### MR state (only for `pipe metrics`)

| Key | Type | Default | Spec |
|---|---|---|---|
| `mr_state.gitlab.url` | `https://` URL | unset (the metric prints `n/a`) | 003 |
| `mr_state.gitlab.token` | `keychain:<service>` | unset | 003 |

## 3. Constants in code (not config)

| Name | Value | Where |
|---|---|---|
| `MAX_HOP_FREE` | 3 | 003 `core/source.py` |
| `MAX_HOP_TEMPLATE` | 5 | 003 `core/source.py` |
| `CLAIM_SETTLE_S` | 2 | 003 |
| `OWNER_OFFLINE_AFTER_S` | 60 | 003 |
| `MAX_GOAL_CHARS` | 500 | 003 |
| `MAX_CONTEXT_TEXT`, `MAX_CONTEXT_TOTAL` | 1000, 4000 | 003 |
| `MAX_PROPOSAL_CHARS` | 4000 | 003 |
| `MAX_TITLE_CHARS`, `BRANCH_PREFIX` | 100, `pipe/` | 004 (claude adapter) |
| `MAX_TEMPLATE_BYTES`, `MAX_TEMPLATE_GOAL`, `MAX_TEMPLATE_STEPS` | 20000, 300, 6 | 006 |
| Upload root, upload size limit | `~/.pipe/run/`, 10 MB | 001 FR-024 |
| Poll interval of the wiz-review wrapper | 15 s | 005 |

## 4. Files and directories

| Path | Use | Spec |
|---|---|---|
| `~/.pipe/config.yaml` | the config above | 001 |
| `~/.pipe/state.json`, `~/.pipe/seen.json` | local state | 001 |
| `~/.pipe/run/` | the only root for `upload_file` | 001 |
| `~/.pipe/worktrees/<run_id>/` | one worktree for each `write` run, removed after the run | 004 |
| `~/.pipe/flows/<name>.yaml` | owner override of a flow template (wins by name) | 006 |
| `flows/*.yaml`, `flows/tags.yaml` | shared templates and the tag vocabulary, in git | 006 |

## 5. Inputs of the trigger template (CI side, spec 005)

The template [gitlab-ci.yml](../templates/trigger/gitlab-ci.yml) passes values as flags of `post_trigger.py`: `--token-env`, `--channel`, `--agent`, `--title`, and one of `--flow` or `--pipeline-file`. Only the token is a variable (`SLACK_TRIGGER_TOKEN`, masked).

## 6. Reason codes

`failed` reasons: `needs_input` (a `waiting` reason, not a failure), `dialog_timeout`, `run_failed`, `invalid_proposal`, `invalid_payload`, `invalid_result`, `timeout`, `no_claimer`, `rejected`, `interrupted`, `capability not available`, `hop limit exceeded`, `hop limit exceeded (plan source not verified)`, and the delegation reasons of spec 004 (`repo not available`, `unknown_target`, `target_required`, `base not available`, `worktree failed`, `no changes`, `branch changed`, `commit failed`, `push failed`, `no merge request`), `upload refused` (spec 005).

Ignore reasons (logged, never posted): `excluded`, `bad_branch`, `already_branched`, `rejected`, `bad_proposal`, `duplicate_handoff`, `not_claimant`, `not_trigger`, `trigger_not_agent`, `no_card`, `bad_payload`, `by_mismatch`, `not_planner`, `not_assigned`, `not_for_me`, `unsupported_access`, `not_allowed`.

Only `run_failed` (a runtime result with `status: failed`) takes the `on_fail` branch. A non-zero exit of an `exec` capability gives `RuntimeFailed` and no branch.

## 7. Message types (spec 003 `contracts/task-metadata.md`)

| Type | Meaning |
|---|---|
| 1, 2, 3 | Plan, rejected plan, start handoff |
| 4 | Step claim. With `needs_approval` and `write` it is the owner gate of spec 004 (buttons `pipe_accept`, `pipe_reject`) |
| 5 | Step result. `needs_approval` is a `gate: approval` step or a plan proposal (✅ release posts a NEW type 5 `done`) |
| 6 | Approval request for the human step |
| 7, 8, 9 | Waiting (owner offline), hop refusal, no claimer |
| 10 | Dialog question |
| 11 | Branch handoff (`failed`, `run_failed`, `next`, `hop + 1`, no button) |
