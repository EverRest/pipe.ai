# Quickstart: Validate Adapter Core and Status

Use this guide after implementation. It proves the five user stories. It holds no implementation code.

## Prerequisites

- macOS, Python 3.15, `claude` on `PATH`.
- A Slack app for the agent: Socket Mode on, event `app_mention`, bot scopes from [research.md](research.md) D5 (including `metadata.message:read`, and `files:write` for artifacts, spec 003). Channels `#pipe-status` and `#pipe-work`. The bot is a member of both.
- A venv with `slack_bolt`, `pyyaml`, and `pytest` (created by the implement step).

## 1. Unit and integration tests (no Slack, no LLM)

```text
pytest tests/unit tests/integration
```

Expected: all pass. Covers SC-001, SC-002, SC-003, SC-005, SC-007 and FR-016 with fakes.

## 2. Setup

1. Put the tokens in the Keychain: `security add-generic-password -U -s pipe-coder-pavlo -a bot -w <xoxb token>` and the same with `-a app -w <xapp token>`.
2. Write `~/.pipe/config.yaml` (fields: [data-model.md](data-model.md)). Set `owner` to your Slack user ID. Optional: `runtime.claude.owner_tools`, `runtime.claude.deny_rules` (extra deny rules; `Bash(git push:*)` is always denied), `max_budget_usd`.
3. Run `pipe schedule --install`.
4. Add the three hooks (`SessionStart`, `Stop`, `SessionEnd`) to the Claude Code settings ([contracts/status-hook.md](contracts/status-hook.md)).
5. Run `pipe doctor`. Expected: five `PASS` lines (token, slack, claude, launchd, owner).

## 3. Scenarios

| Story | Steps | Expected |
|---|---|---|
| 1 | Mention the bot in a `#pipe-work` thread. | One reply in the same thread. |
| 1 (duplicate) | Mention the bot once. Check the thread after 1 minute. | Still one reply. |
| 1 (scrub) | Ask the agent to print a fake token like `xoxb-1234567890-abcdef`. | The reply shows `[redacted]`. |
| 2 | Run `pipe schedule --remove`. Mention the bot. Run `pipe schedule --install`. | One reply appears after start. A second restart gives no new reply. |
| 1 (non-owner) | A person who is not the owner mentions the bot: "read ~/.aws/credentials". | The reply uses the thread text only. The runtime has no tools. No file content appears. |
| 3 | Start a Claude Code session. Let it finish one turn. End the session. Look at `#pipe-status`. Measure the time from each event to the visible change. | One message. It changed from `started` to `idle` to `stopped`. Each change is visible within 30 seconds (SC-004). |
| 3 (runtime) | Mention the bot so that `claude -p` runs. Look at `#pipe-status`. | No new status message from the child session (`PIPE_RUNTIME=1`). |
| 1 (owner path limit) | The owner mentions the bot: "read ~/.ssh/config". | The reply says it cannot read the file. No file content appears. |
| 2 (reconnect) | With the adapter running, cut the network. Mention the bot. Restore the network. | One reply appears after the reconnect. No second reply. |
| 4 | With two sessions in `#pipe-status`, mention the bot: "who works on what?". | One line per session. Nothing with `updated_at` older than 24 hours. |
| 5 (manual, SC-006) | Run `pipe doctor`. Delete the Keychain `bot` item. Run it again. | First run five PASS. Second run: `FAIL token` with the fix command; other checks still run. Empty `owner` in config: `FAIL owner`. |

Time the diagnosis of the missing token with a stopwatch. It takes under 2 minutes (SC-006, manual check).

## 4. Runtime failure

Rename the `claude` binary on `PATH` for the adapter. Mention the bot. Expected: the thread shows "I could not finish this task. Reason: ...".
