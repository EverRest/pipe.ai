# Contract: CLI `pipe`

Entry point: `~/.pipe/bin/pipe` (launcher) runs `python -m pipe.cli`.

| Command | Purpose | Exit code |
|---|---|---|
| `pipe run` | Start the adapter: connect Socket Mode, run catch-up, handle mentions. Long process. | 0 on stop, non-zero on fatal error |
| `pipe doctor` | Run five checks and print one line per check. All checks run even after a failure. | 0 if all pass, 1 if one fails |
| `pipe schedule --install` / `--remove` | Write or remove the launchd plist and the launcher. | 0 / 1 |
| `pipe flows [show <name> \| validate [<name>]]` | List, show, and check flow templates (spec 006, [contracts/cli.md of 006](../../006-flow-catalog/contracts/cli.md)). Read-only. No form writes or deletes a template. Spec 001 owns the dispatch. Spec 006 owns the handler. Without the handler: prints `flows: not installed`. | 0 if all templates are valid, 1 if one is invalid or the handler is missing |
| `pipe status-hook <SessionStart\|Stop\|SessionEnd>` | Hook entry. Exits 0 at once when `PIPE_RUNTIME` is set and non-empty. See [status-hook.md](status-hook.md). | Always 0 |

## `pipe doctor` output

```text
PASS token: Slack bot and app tokens found in Keychain (service pipe-coder-pavlo)
PASS slack: auth.test ok as <bot name>; #pipe-status found
PASS claude: claude found at <path>
PASS launchd: job com.pipe-ai.adapter loaded
PASS owner: owner is set (<Slack user ID>)
```

A failed line starts with `FAIL` and gives the cause and the fix command. Examples: `FAIL owner: config key owner is empty. Every sender gets no tools. Set owner to your Slack user ID in ~/.pipe/config.yaml`; `FAIL token: no Keychain item for service pipe-coder-pavlo, account bot. Run: security add-generic-password -s pipe-coder-pavlo -a bot -w <token>`. Output never prints a token value.

Checks:
1. `token`: `security find-generic-password` finds both items; config has no plain token.
2. `slack`: `auth.test` with the bot token; `#pipe-status` exists and the bot is a member. Skipped with `FAIL` (not crash) if check 1 failed.
3. `claude`: `shutil.which("claude")`.
4. `launchd`: plist exists, is current (points to the launcher), and `launchctl print gui/<uid>/<label>` succeeds.

5. `owner`: the config key `owner` is a non-empty Slack user ID. Fails when it is empty (every sender would get no tools).

Label: `com.pipe-ai.adapter`.
