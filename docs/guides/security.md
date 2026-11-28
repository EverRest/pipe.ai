# Security

## Trust rules

- Thread text is untrusted. The prompt puts it in an escaped `<thread>` block.
- The adapter trusts task metadata only from a bot with a valid card, and only when `by` equals the sender.
- Every bot that can post a card in the agents channel is a trusted agent. Control who can join that channel and which apps the workspace allows.
- Every adapter checks a template source against its own files. If the check fails, the plan is `free`.
- Gate buttons work only for the owner of the agent.

## Owner gate

A `write` step runs with no button only in these cases:

1. The owner started the thread, and every other message in it is from the owner or this agent.
2. The sender agent is in `allowlist`, the starter is the owner of the sender agent or is in `allowlist`, and every other sender in the thread is the owner or is in `allowlist`.

In all other cases the owner of the agent clicks Accept or Reject.
A trigger plan from a bot that is not in `allowlist` also needs Accept.

## Plan release

- Only the thread starter or the owner of the planner agent can release a plan with the check mark.
- A runtime result never starts a delegation. Only plan steps do.

## Tools and exposure

- A skill or a command is exposed automatically when its `allowed-tools` holds only `Read`, `Grep`, `Glob`, and its text has no credential signal. Check `pipe capabilities`.
- All other items are `owner-only` until you list them in `exposed`.
- A run for a non-owner gets no file tools. It loads only the capability of the step.
- The owner path tools apply only inside `repo_roots`.
- Default deny rules: `Bash(git push:*)`, `Bash(git -C:*)`, `Bash(git -c:*)`, `Bash(env:*)`, `Bash(sh:*)`, `Bash(bash:*)`, `Bash(zsh:*)`. You can only add rules. A deny list is not a security guarantee.
- The adapter denies edits in `.claude` directories.
- The git commands of the adapter disable repository hooks.
- `upload_file` accepts only regular files in `~/.pipe/run/`, at most 10 MB.

## Secrets

- Slack tokens and capability tokens are in the macOS Keychain.
- The adapter replaces token-like strings with `[redacted]` before it posts.
- The scrub uses patterns. It cannot find every secret form.

## Known residual risks

- A `read` step that a different person starts has no owner gate. Exposure is the limit. Set `max_budget_usd`.
- An exposed plugin ID exposes all its skills, also a skill that uses credentials.
- An `exec` capability runs as your OS user with no sandbox.
- There is no rate limit for a leaked trigger token. Remove the bot from `allowlist` and rotate the token.
- The `.git` check does not cover the shared repository config under `.git/worktrees/`.

Review the full list in [docs/HANDOFF.md](../HANDOFF.md) section 5 before the first real use.
