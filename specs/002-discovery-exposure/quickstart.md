# Quickstart: Validate Discovery and Exposure

Use this guide after implementation. It proves the three user stories. It holds no implementation code. Spec 001 must be installed and working (`pipe doctor` passes).

## Prerequisites

- Spec 001 quickstart done. The bot is in `#pipe-agents` (create the channel if needed). Add the bot scopes `pins:write`, `pins:read`, and `im:write` (add `groups:history` and `groups:read` for a private channel). `chat:write` is already present from 001. Check that it is still in the list. Reinstall the Slack app after a scope change.
- `claude` on `PATH` (flags: [research.md](research.md) "Checked on this machine").

## 1. Unit and integration tests (no Slack, no LLM)

```text
pytest tests/unit tests/integration
```

Expected: all pass. Covers SC-001 to SC-004, SC-006, FR-001 to FR-020, and the `claude` command flags with the stub script.

## 2. Scenarios

| Story | Steps | Expected |
|---|---|---|
| 1 | Run `pipe capabilities`. | One list with plugins, skills, commands, MCP servers, repos. Each line shows `exposed` or `owner-only`. No path, URL, or token. |
| 1 | Add a skill directory with a `SKILL.md` to `~/.claude/skills`. Run `pipe capabilities` again. | The new skill is in the list. |
| 2 | Look at the MCP lines of the list. | Every MCP server is `owner-only`. |
| 2 | Add one MCP server ID to `exposed` in `~/.pipe/config.yaml`. Restart the adapter (`pipe schedule --remove`, then `--install`). Read the card in `#pipe-agents`. | The server is in the card `skills`. The card has no URL. |
| 2 | Remove the ID from `exposed`. Restart. | The server leaves the card. The same card message is updated. |
| 2 | Add an unknown ID to `exposed`. Run `pipe capabilities`. | `NOTICE unknown_id` names it. The card is unchanged. |
| 3 | Start the adapter with no card. | One card is posted and pinned in `#pipe-agents`. |
| 2 | Add a plugin ID (for example `plugin:ponytail`) to `exposed`. Restart. | All skills of that plugin are in the card. A credential-backed skill of it is in the card, and `NOTICE credential_exposed` names it. |
| 2 | Add a repo ID to `exposed`. Run `pipe capabilities`. | `NOTICE not_exposable` names it. The repo stays `owner-only` and is not in the card. |
| 2 | Edit an exposed skill that was clean: add the word `token` to its body. Restart. | If you listed it by name: it stays in the card and a notice appears. If it was exposed only as clean: it leaves the card. |
| 2 (FR-019) | Start the adapter. Read your Slack DMs. | One DM from the bot with the counts and the notices. |
| 2 (FR-020) | Restart 10 times with no change. | No new DM. Then add an unknown ID to `exposed` and restart: one new DM. |
| 3 | Add a skill that has `allowed-tools: Read` and no credential words. Restart. | The same card shows the skill. No second card. |
| 3 (FR-023) | Expose a plugin skill that has no `tags`. Add `tags: {<its id>: [review]}` to `~/.pipe/config.yaml`. Restart. | The same card shows the tag `review` on that skill. |
| 3 (FR-023) | Add a tag map entry for a skill that has frontmatter `tags`. Restart. | The card shows the map list in place of the frontmatter tags. The type and plugin tags stay. |
| 3 (FR-023) | Add an unknown ID to `tags`. Run `pipe capabilities`. | `NOTICE unknown_tag_id` names it. The card is unchanged. |
| 3 | Restart again with no change. | The card is not edited (no "edited" mark). |
| 3 | Restart 10 times. | One card. |
| 3 | Delete the card message. Restart. | A new card is posted and pinned. |
| 3 | Unpin the card. Restart. | The card is pinned again. |
| 3 | Delete `~/.pipe/state.json` key `card`. Restart. | The adapter finds the old card. No second card. |
| 3 (FR-021) | Read the metadata of the card. Check the Slack app scopes. | The metadata has `bot_user_id` (the Slack user ID of the bot). The scope list has no `users:read`. |
| 3 (SC-003) | Copy the text of the card and its metadata. Search for `http`, `xox`, `/Users`, `~/`. | No match. |
| 4 | Add one `exec` entry to `capabilities` in `~/.pipe/config.yaml` (an absolute `command` list, `access: read`, one `input_schema`). Run `pipe capabilities`. | The line `owner-only exec exec:<id> <name>` appears. No command is printed. |
| 4 | Add `exec:<id>` to `exposed`. Restart. Read the card. | The card has the entry with `access` and `input_schema`. It has no `command`, no URL, no environment name, and no runtime kind. The same card message is updated. |
| 4 | Add one `http` entry with `token: keychain:<service>`. Expose it. Restart. | The card has the entry. The scan for `://`, `xox`, `/Users`, `~/` finds nothing in the card. (The tag `http` of the capability is allowed: it is not a URL.) |
| 4 | Remove the `input_schema` of the exposed `exec` entry. Restart. | The config load fails: `capability exec:<id> is exposed and has no input_schema`. |
| 4 | Set `access: write` on a declared entry, or a plain `http://` URL for another host. | The config load fails and names the entry `id`. |
| 4 | Put a plain token in `token`, a shell string in `command`, or `$ref` in a schema. Run `pipe capabilities`. | The config load fails and names the entry `id`. The message holds no value. |
| size | Put 30 exposed skills in the config. Restart. | The card posts, or the log shows a clear error. (research.md A1) |

## 3. Load exposed capabilities into a `--restricted` child (manual, real `claude`)

This check proves [contracts/runtime-load.md](contracts/runtime-load.md). It repeats research.md P3, P4, P8, P9 with real exposed items. 002 does not load capabilities into live runs, so only the helper runs this check. A short helper is in the implementation tasks (T038).

1. Expose one skill and one MCP server in `exposed`.
2. Run the helper. It builds the command with `PreparedLoad` and runs a prompt that asks for the exposed skill.
3. Expected: the exposed skill runs. A skill that is not exposed gets a denial. The exposed MCP tools exist. No other MCP tool exists. The run dir is removed after the run.
4. Check that `ls ~/.pipe/run` is empty after the run.
