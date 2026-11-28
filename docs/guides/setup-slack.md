# Set up Slack

This procedure is manual. Nobody tested it with a live workspace. The Slack screens can change.
The source for the scopes is [docs/reference.md](../reference.md).

## 1. Create the channels

Create these channels. You can use other names. Then set the same names in `~/.pipe/config.yaml`.

| Channel | Config key | Use |
|---|---|---|
| `pipe-work` | `work_channel` | Tasks, plans, steps. |
| `pipe-agents` | `agents_channel` | Agent cards. This channel is a trust boundary. |
| `pipe-status` | `status_channel` | Session status. |

The channel `#pipe-library` is only for release announcements (spec 007). The adapter does not read it.

## 2. Create the app for an agent

Make one app for each agent adapter.

1. Create a Slack app.
2. Turn on Socket Mode.
3. Create an app-level token with the scope `connections:write`. It starts with `xapp-`.
4. Add the bot scopes from the table.
5. Subscribe to the bot events `app_mention` and `reaction_added`.
6. Turn on Interactivity. Socket Mode needs no request URL.
7. Install the app. Copy the bot token. It starts with `xoxb-`.
8. Invite the bot to `pipe-work`, `pipe-agents`, and `pipe-status`.

Install the app again after each change of scopes.

| Bot scope | Use |
|---|---|
| `app_mentions:read` | Mention events. |
| `chat:write` | Post, update, delete own messages. |
| `channels:history` | Read channels and threads. |
| `channels:read` | Find channels. |
| `metadata.message:read` | Read task and card metadata. |
| `files:write` | Upload run files. |
| `pins:write`, `pins:read` | Pin and find the agent card. |
| `im:write` | Send the summary DM to the owner. |
| `reactions:read` | Check mark release. |
| `groups:history`, `groups:read` | Private channels. |

Do not add `users:read`.

Unverified: the code asks for public and private channels together. If the log shows `missing_scope`, add `groups:read`.

## 3. Store the tokens in the Keychain

The service name must match `slack_tokens: keychain:<SERVICE>`. The account names are `bot` and `app`.

```sh
security add-generic-password -U -s <SERVICE> -a bot -w <BOT_TOKEN>
security add-generic-password -U -s <SERVICE> -a app -w <APP_TOKEN>
```

Do not put a token in a file. Remove these commands from the shell history.

## 4. Find the IDs

- `owner` in the config is your Slack user ID (`U...`).
- `allowlist` holds bot IDs (`B...`) or user IDs.
- A trigger needs the channel ID and the user ID of the agent bot. The agent card in `pipe-agents` holds `bot_user_id` in its metadata.

## 5. Create the trigger bot app (optional)

A CI job uses this app to start a pipeline.

1. Create a second app, for example `pipe-gitlab`.
2. Add the bot scope `chat:write`. The reference also lists `pins:write`, but the script does not pin.
3. Do not turn on events or Socket Mode.
4. Install the app. Invite the bot to `pipe-work` and `pipe-agents`.
5. Save the bot token as a masked CI/CD variable.

### Post the trigger card one time

Run this on a machine with the project venv. Put the token in an environment variable first.

```sh
.venv/bin/python templates/trigger/post_trigger.py card \
  --token-env <TOKEN_VAR> \
  --agents-channel <CHANNEL_ID> \
  --owner <OWNER_USER_ID> \
  --bot-user-id <TRIGGER_BOT_USER_ID> \
  --name <TRIGGER_NAME>
```

### Add the CI job

Copy [templates/trigger/gitlab-ci.yml](../../templates/trigger/gitlab-ci.yml) and `post_trigger.py` to the CI repository.
The example runs only for a schedule.

- It reads the token from `SLACK_TRIGGER_TOKEN`. The `--token-env` flag sets this name.
- Replace `<CHANNEL_ID>` and `<AGENT_USER_ID>`.
- Give exactly one of `--flow <name>` or `--pipeline-file <file.json>`.
- Give `--title`.

The reference lists the variables `PIPE_TRIGGER_TOKEN`, `PIPE_CHANNEL`, `PIPE_AGENT_USER_ID`, `PIPE_FLOW`, `PIPE_PIPELINE_FILE`, and `PIPE_TRIGGER_TITLE`. The shipped template and script do not read them by name.

To start with no button, add the bot ID of the trigger bot to `allowlist` of the agent.

## 6. Check

Run `pipe doctor`. It does not connect to Slack.
Then start `pipe run`. Look for the card in `pipe-agents` and for errors in `~/.pipe/logs/adapter.log`.

Do this check early: does Slack send `app_mention` for a mention that a bot posts? A trigger and a fast handoff need it.
In the work channel, a wake pass each 60 seconds also finds handoffs and triggers. A live test did not prove this.
