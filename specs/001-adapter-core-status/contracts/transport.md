# Contract: Transport (core to chat system)

Source: constitution principle XI (version 1.2.0), spec FR-020, FR-021. The first adapter is Slack (`transport_slack_*`). Future adapters (for example Discord and Telegram) are not in scope. This contract adds no operation for them.

## Rule

- The core does not import a chat product. The core does not name one.
- The core talks to the chat system only through the Protocol `ports.Transport`.
- The core does not read raw chat fields. The transport adapter maps them to the neutral types below.
- Trust rules stay in the core. They use `sender_id`, `sender_is_bot`, and `card_owner_id`.
- The import-boundary test (spec 003, task T071) forbids a core import of every `pipe.transport_slack*` module.

## Neutral types (`src/pipe/core/contract.py`)

| Type | Fields |
|---|---|
| `Message` | `channel`, `ts`, `thread` (equals `ts` for a top-level message), `sender_id`, `sender_is_bot`, `sender_handle` (may be `None`), `text`, `metadata` (`{event_type, event_payload}` or `None`), `reactions` (list of `{name, users}`), `event_id` (may be `None`) |
| `Identity` | `agent_id` (the id of this agent in the transport), `handle` (the mention handle of this agent) |
| `Button` | `action_id`, `label` |
| `MentionEvent` | the fields of `Message`, as an event |
| `ReactionEvent` | `event_id`, `channel`, `item_ts`, `sender_id`, `name` |
| `ClickEvent` | `event_id`, `channel`, `message_ts`, `sender_id`, `action_id` |
| `UploadRefused` | Exception of `upload_file` for a path outside the upload roots, a symbolic link, a directory, or a file over 10 MB |

`ts` is a string: seconds, a dot, and six digits of microseconds. Every transport MUST produce this format. The core compares `ts` as numbers.

## Operations (`ports.Transport`)

The port holds only the operations that specs 001 to 006 use.

| Operation | Use | Slack adapter |
|---|---|---|
| `whoami() -> Identity` | Own identity at start | `auth.test` (`bot_id`, `user_id`) |
| `find_channel(name) -> channel_id` | Find a channel by name | `conversations.list` |
| `member_channels() -> list[channel_id]` | Catch-up scope | `users.conversations` |
| `post_message(channel, text, thread=None, metadata=None, buttons=None) -> ts` | Reply, card, plan, step, buttons | `chat.postMessage` (buttons become Block Kit) |
| `update_message(channel, ts, text, metadata=None, buttons=None)` | Status, card, step state | `chat.update` |
| `delete_message(channel, ts)` | Remove a lost claim | `chat.delete` |
| `history(channel, oldest=None, limit=None) -> list[Message]` | Read a channel with metadata (cards, status, catch-up, metrics) | `conversations.history` with cursor and `include_all_metadata` |
| `replies(channel, thread, oldest=None) -> list[Message]` | Read a thread with metadata and reactions | `conversations.replies` with cursor |
| `pin(channel, ts)`, `list_pins(channel) -> list[ts]` | Pin the card | `pins.add`, `pins.list` |
| `send_dm(user_id, text)` | DM to the owner | `conversations.open`, `chat.postMessage` |
| `upload_file(channel, thread, name, data, title) -> link` | Send an artifact (screenshot, report) into a thread. `data` is `bytes` or a `Path`. Returns an `https://` link for `artifacts`. | `files_upload_v2` (scope `files:write`) |
| `on_event(handler)` | Receive `MentionEvent`, `ReactionEvent`, `ClickEvent` | Socket Mode: `app_mention`, `reaction_added`, `block_actions` |
| `on_reconnect(callback)` | Run catch-up after a link loss | Socket Mode reconnect listener |
| `mention(handle) -> str` | Text that mentions an agent | `<@handle>` |
| `escape_mentions(text) -> str` | Remove all mention and broadcast syntax | `<!channel>`, `<!here>`, `<@U..>` and so on |
| `id_pattern: str` | Valid form of a `sender_id` (used to check the `allowlist` config key) | `^[BUW][A-Z0-9]{2,}$` |

`mention` and `escape_mentions` are pure. Core code that builds text gets them as an injected `Formatter`. The core never writes mention syntax itself.

## `upload_file` rules

- Source: owner decision of 2026-11-26. The first parameter `channel` is added to the owner signature `upload_file(thread, name, data, title)`, because every other operation names the channel with the thread.
- The result is the link of the uploaded file. The caller puts it in `artifacts`. The core carries links only and never reads a file.
- `name` and `title` pass `scrub` (FR-024). The content is not scanned. A screenshot or a report is the responsibility of the capability that made it.
- A `Path` MUST be a regular file, not a symbolic link, inside the upload roots of the adapter (default `~/.pipe/run/`), and at most 10 MB. Else the adapter raises `UploadRefused` and sends nothing. `bytes` have the same size limit.
- Slack: the adapter uses the external upload flow (`files_upload_v2`) and the bot scope `files:write`. It never calls the old `files.upload`.
- `FakeTransport.upload_file` records the call (no content) and returns a fixed link.

## Identity mapping (Slack adapter)

| Neutral | Slack source |
|---|---|
| `sender_id` | `bot_id` when the message has one, else `user` |
| `sender_is_bot` | `bot_id` is set |
| `sender_handle` | `user` (for a bot message, the bot user ID) |
| `card_owner_id` | the card field `owner` (a Slack user ID in the Slack adapter) |
| `event_id` | the Socket Mode envelope `event_id` (the dedupe source) |
| `Identity.agent_id`, `Identity.handle` | `auth.test` `bot_id`, `user_id` |

The card wire fields keep their names `bot_id` and `bot_user_id` (design brief §5.3). The core reads them as the opaque `agent_id` and `handle`. The trust check "message `sender_handle` equals card `bot_user_id`" is a core rule (spec 003 task T007). It uses the neutral fields.

## Slack adapter modules

| Module | Role |
|---|---|
| `src/pipe/transport_slack.py` | `Transport` over `slack_sdk.WebClient` (I/O) |
| `src/pipe/transport_slack_events.py` | `slack_bolt` Socket Mode handlers. They map Slack events to the neutral events and register the reconnect listener (I/O) |
| `src/pipe/transport_slack_map.py` | Pure mapping: Slack message to `Message`, buttons to Block Kit, `mention`, `escape_mentions`, the `event_id` source |
| `src/pipe/transport_slack_http.py` | `call_slack(method, payload)` over `urllib` for the status hook. It imports no `slack_bolt` and no `slack_sdk` |

Scopes, event subscriptions, and Socket Mode belong to the Slack adapter only. They are in [../research.md](../research.md) D5 and in the quickstarts of specs 002 and 003.

## Test double

`FakeTransport` (`tests/fakes.py`) is the in-memory `Transport`. It is the former `FakeSlack` of this spec, renamed. It records every call, keeps messages in memory, serves `history` and `replies` with cursor pages of 100, and can raise events. Unit and integration tests of the core use it. No test of the core needs Slack.
