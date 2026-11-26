# Contract: CLI additions

Extends [../../001-adapter-core-status/contracts/cli.md](../../001-adapter-core-status/contracts/cli.md) and [../../002-discovery-exposure/contracts/cli.md](../../002-discovery-exposure/contracts/cli.md).

| Command | Purpose | Exit code |
|---|---|---|
| `pipe metrics [--weeks N]` | Read `#pipe-work` and the MR state (from the configured provider; GitLab is the first). Print the four experiment metrics. Read-only. Default `--weeks 4`. | 0 on success, 1 if Slack cannot be read |
| `pipe run` | Unchanged command. New behavior: handles `reaction_added` and button clicks, routes every event through `route`, runs the `wake` pass at start and after each reconnect. The config gets the sections `runtime` and `mr_state` (data-model.md). | unchanged |

## `pipe metrics` output

```text
useful delegations per week  : 2.5 (threshold >= 3)          below
  2026-W46: 2   2026-W47: 3
pipelines without manual help: 60% of 5 (threshold >= 50%)   ok
noisy agent messages         : 4% of 50 (threshold < 10%)    ok
threads stopped by hop limit : 0 (threshold 0)               ok
owner offline wait, median   : 12 min over 3 waits           track
  open waits: 1
```

Rules:
- The command reads `~/.pipe/config.yaml` for `work_channel`, the section `mr_state` (`provider`, `gitlab.url`, `gitlab.token`), and the Slack tokens (Keychain, from 001). It reads no `runtime` key.
- It counts only trusted task messages (a card exists for the author). It reads the `artifacts` links of those messages.
- A metric with no data prints `n/a`.
- Without `mr_state.gitlab.url` or `mr_state.gitlab.token`, the delegation metric prints `n/a (MR state provider not configured)`. The other metrics still print.
- The GitLab provider calls GitLab only for URLs whose host equals the host of `mr_state.gitlab.url`. It sends the token only to that host. It skips other URLs and prints a count of skipped URLs.
- It never prints a token, a thread text, or an MR title.

## Other commands and keys of the second batch (2026-11-26)

- `pipe flows [show <name> | validate [<name>]]`: spec 001 owns the dispatch, spec 006 owns the handler. Read-only.
- Config key `dialog_timeout_h` (default 24): [../data-model.md](../data-model.md). `pipe doctor` does not check it.
- `pipe metrics` is unchanged. A pipeline stopped by the `hop` limit still counts as a `hop_stop`. A dialog wait is not manual help (Q8 = a): a human answer to a question is a reply, not a "manual help between steps". The metric `clean_pipelines_share` ignores a message that a valid dialog answer made (the answer is part of the pipeline).

## Slack app additions (one-time, done by the owner; these belong to the Slack transport adapter)

- Bot scope: `reactions:read`. For a private `#pipe-work`: `groups:history`, `groups:read`. Do not add `users:read`: the mention of the next agent uses `bot_user_id` from the card.
- Event subscription: `reaction_added`.
- Interactivity: on (Socket Mode needs no request URL).
- Reinstall the app after the change.

Provider config (GitLab, the first provider): a read-only token with scope `read_api`. Store it with `security add-generic-password -s <service> -a token -w <token>`. The value `<token>` is entered by the owner and is never written to a file.
