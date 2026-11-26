# Contract: Status hook and status message

## Hook command

Registered by the owner in Claude Code settings for the events `SessionStart`, `Stop`, and `SessionEnd`:

```text
~/.pipe/bin/pipe status-hook SessionStart
~/.pipe/bin/pipe status-hook Stop
~/.pipe/bin/pipe status-hook SessionEnd
```

- Runtime: the hook runs with the venv Python through the launcher, like the adapter. It may import `pyyaml` and `pipe.*`. It does not import `slack_bolt` or `slack_sdk`.
- Guard: if the environment variable `PIPE_RUNTIME` is set and non-empty (the adapter sets `PIPE_RUNTIME=1` in the `claude -p` child), the hook exits 0 at once. It reads no stdin, calls no Slack API, and writes no file.
- Input: one JSON object on stdin. Used keys: `session_id`, `cwd`. (`hook_event_name` is also read; the argument wins.) Assumption A1 in [research.md](../research.md).
- Output: nothing on stdout. Exit code always 0. Errors go to `~/.pipe/logs/hook.log`.
- Slack call: the hook entry takes an injected function `call_slack(method, payload) -> dict`. The default is `call_slack` of `src/pipe/transport_slack_http.py` (the Slack adapter): `urllib.request` with a 5 second timeout. The hook is not core. Tests pass a recording fake (`FakeCallSlack`). One Slack call per event.
- Channel: the hook uses the name `#pipe-status` until the channel ID is cached in `~/.pipe/state.json` (`status_channel_id`). After the first post, it writes the ID from the Slack response.
- Lock: the first post for a `session_id` uses the lock file `~/.pipe/status/<session_id>.lock` (`O_EXCL`). A second concurrent first call waits for the state file (up to 5 seconds) and then does `chat.update`. Two concurrent first calls post one message. The hook owns lock cleanup: it removes the lock after it saves the state file, and it removes a lock whose file mtime is older than 30 seconds before it creates a new one. The adapter never touches lock files.

## Behavior

| Event | State file | Slack call | Result |
|---|---|---|---|
| `SessionStart` | missing | `chat.postMessage` to `#pipe-status` with `metadata` | Save `channel`, `ts`. |
| `SessionStart` | exists | `chat.update` | Same message, stage `started`. |
| `Stop` | exists | `chat.update` | Stage `idle`. |
| `Stop` | missing | `chat.postMessage` | Save `channel`, `ts`. Stage `idle`. |
| `SessionEnd` | exists | `chat.update` | Stage `stopped`. |
| `SessionEnd` | missing | `chat.postMessage` | Save `channel`, `ts`. Stage `stopped`. |

Every post and every `chat.update` sets `updated_at` (epoch seconds) in the metadata.

## Message

`text` (for people):

```text
<who> | <repo> | <branch> | <stage> | blocker: <blocker or "none">
```

`metadata`:

```json
{
  "event_type": "pipe.status.v1",
  "event_payload": {
    "v": 1,
    "session_id": "<id>",
    "who": "coder-pavlo",
    "repo": "pipe.ai",
    "branch": "001-adapter-core-status",
    "stage": "started | idle | stopped",
    "blocker": "",
    "started_at": "2026-11-25T10:00:00Z",
    "updated_at": 1795687500
  }
}
```

`started_at` is ISO-8601 UTC. `updated_at` is an integer in epoch seconds.

The payload holds no path, no token, and no URL. `text`, `who`, `repo`, `branch`, and `blocker` pass through `scrub` before the post. Slack mention syntax (`<!channel>`, `<!here>`, `<@U…>`) is escaped in all fields.

## Query

Trigger: a direct mention whose text, after the bot mention is removed, contains `who works on what` as a case-insensitive substring (one rule). The adapter reads `#pipe-status` with `conversations.history` (`oldest` = now minus 7 days, `include_all_metadata=true`, cursor pagination), keeps only messages with `bot_id` set and event type `pipe.status.v1`, keeps only those with `updated_at` in the last 24 hours (the message `ts` is not used), and replies in the thread with one line per session. The reply passes through `scrub`, and mention syntax is escaped. The data is display data only. It is never used as a command (plan Complexity Tracking, principle V). The query reads 7 days because `oldest` filters by message `ts`, and an update does not change `ts`.
