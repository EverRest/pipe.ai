# Contract: CLI additions

Extends [../../001-adapter-core-status/contracts/cli.md](../../001-adapter-core-status/contracts/cli.md).

| Command | Purpose | Exit code |
|---|---|---|
| `pipe capabilities` | Run discovery now. Print the list with the exposure state and the notices. Read-only. No Slack call. | 0 always (a bad item is a notice) |
| `pipe run` | At start (after `auth.test`, before catch-up) run discovery, print the list to `~/.pipe/logs/adapter.log`, sync the card (research.md D10), and send the owner summary DM when it changed (research.md D15). A card or DM error is logged. It never stops the adapter. | unchanged |

## `pipe capabilities` output

```text
exposed     skill    skill:ponytail:ponytail-review      ponytail-review
owner-only  skill    skill:project-context               project-context
owner-only  mcp      mcp:gitlab                          gitlab
owner-only  exec     exec:lint-repo                      Lint repo
owner-only  plugin   plugin:superpowers                  superpowers
owner-only  repo     repo:pipe.ai                        pipe.ai

6 capabilities: 1 exposed, 5 owner-only.
NOTICE unknown_id: skill:old-thing is in exposed but not discovered.
NOTICE unknown_tag_id: skill:old-thing is in tags but not discovered.
```

Rules:
- One line per capability: state, type, `id`, `name`. Sorted by type, then `id`. The type is the part of the `id` before the colon. A declared capability has the type `exec` or `http`.
- The output has no path, URL, token, or description text from a file. It shows names and IDs only.
- Notices follow the list, one per line, with the prefix `NOTICE <kind>:`.
- The command reads `~/.pipe/config.yaml` for `exposed`, `tags`, `capabilities`, `runtime.claude.repo_roots`, and nothing else. It needs no Keychain access and no network.
- A plugin ID in `exposed` shows `exposed` on the plugin line and on each of its skill lines. A repo line is always `owner-only`.

## Owner summary DM (FR-019, FR-020)

- When: at `pipe run` start, after discovery and the card sync.
- To: the config `owner`, through `Transport.send_dm`. (Slack adapter: `conversations.open` with the scope `im:write`, then `chat.postMessage` with the scope `chat:write`.)
- Text: one count line (`N exposed, N owner-only, N skipped`) and one line per notice. Names, IDs, and counts only. It passes `scrub` and `escape_mentions`.
- Send only when the sha256 of the text differs from `summary_hash` in `~/.pipe/state.json`. Write `summary_hash` after a successful post only. A failed post is logged and tried again at the next start.
- No DM when `owner` is empty. The adapter logs it.
- The adapter never stops because of a DM error.
