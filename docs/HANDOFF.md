# Handoff: from specs to implementation

Date: 2026-11-26. State: all six specs have spec, plan, research, data-model, contracts, quickstart, and tasks. The last full analyze pass found no open CRITICAL or HIGH item. No product code exists yet.

## 1. Read in this order

1. `.specify/memory/constitution.md` (v1.3.0). The rules here win over all other files.
2. `docs/design-brief.md`. It gives the architecture, the decision log (§3), and the open questions (§12).
3. `docs/reference.md`. It lists the Slack scopes, the config keys with defaults, the reason codes, and the message types.
4. `specs/00N-*/plan.md`, then `tasks.md` for the spec that you implement.

## 2. Implementation order

Implement the specs one by one. Each spec depends on the specs before it.

| Order | Spec | Tasks | Main result |
|---|---|---|---|
| 1 | `001-adapter-core-status` | 66 | Adapter process, `Transport` port + Slack adapter, `claude` runtime, status hooks |
| 2 | `002-discovery-exposure` | 66 | Capability discovery, exposure rules, agent card |
| 3 | `003-chat-pipelines` | 115 | Planner, plan check, steps, claim, hop, dialog, proposal, branch |
| 4 | `004-delegation` | 55 | Owner gate, allowlist, `write` steps in a worktree, MR |
| 5 | `005-review-gitlab-triggers` | 37 | Slow capabilities (review, e2e), external triggers |
| 6 | `006-flow-catalog` | 63 (52 active) | Flow templates in `flows/`, tag vocabulary, verified source |

Use the Spec Kit skill `speckit-implement` in `.claude/skills/`. Before you run it, set `.specify/feature.json` to the spec directory, for example `{"feature_directory":"specs/001-adapter-core-status"}`.

## 3. Rules for the implementer

- Write the test first. Then write the code (principle VII).
- The core (`src/pipe/core/`) imports no transport and no runtime module. The 003 T071 boundary test checks this.
- Use a venv. The runtime dependencies are only `slack_bolt` and `pyyaml`. The test dependency is `pytest`.
- Keep the Slack tokens in the macOS Keychain. Do not put them in files.

## 4. Manual checks with real services

Do these tasks by hand. Each one needs a real Slack workspace, GitLab, or the `claude` CLI.

| Spec | Tasks |
|---|---|
| 001 | T051 (`claude`), T052 (Slack) |
| 002 | T038 (load probe), T039 (Slack pins, DM) |
| 003 | T067 (`claude`), T068 (Slack), T070 (Slack, two adapters) |
| 004 | T045 (`claude` + `git`), T046 (GitLab), T048 (two owners) |
| 005 | T031 (wiz-review), T032 (trigger bot), T033 (GitLab schedule), T034 (full path) |
| 006 | T060 (planner pick), T061 (2–3 adapters), T062 (two checkouts) |

Risk: Slack may not send `app_mention` for a mention that a bot posts (003 T067–T070). Do this check first. If Slack does not send it, subscribe to `message.channels`. All handoffs between agents depend on this.

## 5. Security decisions to review (🔒)

The owner accepted the recommended option for each item below. Review them before the first real use.

- 002: an exposed plugin ID exposes all its skills. A credential-backed skill in it stays exposed, and the owner gets a notice.
- 002: the `bot_user_id` trust check uses two rules: the card message `user` must equal `bot_user_id`, and the card with the lowest `ts` wins.
- 003 Q6: a `read` step that another person starts has no owner gate. Exposure is the limit. Set `max_budget_usd`.
- 003: the planner always runs `read` with no file tools. A step loads only its own capability.
- 004 DQ2: the gate skips the button only when the sender bot AND the thread starter are trusted.
- 004 DQ6: a runtime result never starts a delegation. Only plan steps do.
- 004 DQ8: `write` steps get no bare `Bash` by default.
- 001: `deny_rules` always includes `Bash(git push:*)`. The owner can only add rules.
- 002/003: declared `exec`/`http` capabilities are `read` only. An exposed `exec` must have an `input_schema`. An `exec` runs as the owner's OS user with no sandbox.
- 005 DQ4: there is no rate cap for a leaked trigger token. Remove the bot from the allowlist and rotate the token.
- 006 DQ1: `hop ≤ 5` applies only when each adapter recomputes the template source from its own files. Otherwise the plan is `free` with `hop ≤ 3`.
- 001: `upload_file` accepts only regular files in `~/.pipe/run/`, at most 10 MB.

## 6. Open items

- §12 of the brief: the Slack plan, and who owns the wiz-review wrapper config.
- `docs/raw.md` (the source idea) is not in this repository.
