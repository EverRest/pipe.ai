# Data Model: Adapter Core and Status

All entities are plain Python dataclasses (frozen) in `src/pipe/core/`. Persistent ones are JSON files under `~/.pipe/`. No database.

## Agent (config)
File: `~/.pipe/config.yaml`.

| Field | Type | Rule |
|---|---|---|
| `agent_name` | str | Required. Used as `who` in status. |
| `slack_tokens` | str | Required. Format `keychain:<service>`. A value that looks like a token (`xox`, `xapp`) is rejected. |
| `owner` | str | Id of the owner in the transport (a Slack user ID in the Slack adapter). Required for tool limits (D8). Without it, every sender gets no tools. `validate_config` warns when it is empty, and `pipe doctor` fails the check "owner is set". |
| `runtime.claude.owner_tools` | list[str] | Default `[Read, Grep, Glob]` (read-only). Tools of the owner. Each item is a non-empty string. The owner can widen the list. `tools_for` uses it for both `tools` and `allowed`. |
| `capabilities` | list | Accepted and ignored in 001. Spec 002 defines and validates declared capabilities (`exec`, `http`). |
| `runtime.claude.deny_rules` | list[str] | Default `[]`. Each item is a non-empty string. Extra rules that the owner adds. The effective deny list is `["Bash(git push:*)"]` plus these items, without duplicates (`effective_deny_rules`). The default entry is ALWAYS present: the owner can only add rules (FR-019). Every owner run denies the effective list with `--disallowedTools`. A non-owner run has no tools, so it needs no deny rule. Specs 003 and 004 read this same key. |
| `max_budget_usd` | number? | Optional, default unset. Must be greater than 0. Passed as `--max-budget-usd` only if set. |
| `runtime.claude.repo_roots` | list[str] | Default `[~/code]`. First entry is the runtime `cwd`. `~` is expanded to an absolute path. The owner run reads only inside these roots (FR-018, research.md D8). |
| `status_channel` | str | Default `pipe-status`. |
| `model` | str? | Optional. Passed to `--model` only if set. Must match `^[A-Za-z0-9][A-Za-z0-9._\[\]-]*$`. |
| `step_timeout_min` | int | Default 30. Minimum 1. |
| `allowlist`, `exposed` | list | Accepted and ignored in 001 (brief §5.4). Specs 002 to 004 use them. |

The keys `runtime.claude.owner_tools`, `runtime.claude.repo_roots`, and `runtime.claude.deny_rules` sit in the section `runtime.claude` (brief §5.4). Only the `claude` runtime adapter reads this section. The core never reads it. 001 reads only these three keys in it. 001 also reads `runtime.claude.deny_rules` (FR-019). Other keys in `runtime` (`name`) are added by spec 003. The old top-level keys `owner_tools` and `repo_roots` are an error: the message names the new path. No fallback exists, because a silent default for `repo_roots` would widen the file limit.

## LocalState
File: `~/.pipe/state.json`.

| Field | Type | Rule |
|---|---|---|
| `last_seen_ts` | str (a message `ts`) | Moves forward only. Set to start time on first start (no old history is answered). Saved after each reply, in the live path and in the catch-up path. |
| `bot_user_id` | str | From `auth.test` at start. |
| `status_channel_id` | str | Cached from `conversations.list`. |

## SeenSet
File: `~/.pipe/seen.json`.

| Field | Type | Rule |
|---|---|---|
| `event_ids` | list[str] | Last 500, oldest dropped. |
| `mention_keys` | list[str] | Format `<channel>:<ts>`. Last 500. |
| `in_flight` | set[str] | Memory only. Never written to the file. At receipt, the adapter adds the `event_id` and the mention key here. It moves them to `event_ids` and `mention_keys` (and writes the file) only after the reply or the failure message is posted. After a crash, the set is empty, so the restart answers the mention once. `pick_missed` keeps its check "a bot reply exists after the mention" as the guard against a duplicate. |

## MentionEvent (input to the router)
| Field | Type |
|---|---|
| `event_id` | str? (None in catch-up) |
| `channel` | str |
| `ts` | str |
| `thread_ts` | str (equals `ts` for a top-level message) |
| `sender_id` | str (the sender) |
| `sender_is_bot` | bool (true when a bot sent it) |
| `text` | str |

The transport adapter makes this event from its own message. See "Transport-neutral identities" below. The core never reads a raw chat field.

Rules (`router.should_handle`):
1. Ignore if `sender_is_bot` is true or `sender_id` is the agent itself.
2. Ignore if `event_id` is in `event_ids` or in `in_flight`.
3. Ignore if `<channel>:<ts>` is in `mention_keys` or in `in_flight`.
4. Ignore if the text has no mention of the agent (`Transport.mention(handle)`).
5. Otherwise handle. Result: `Decision(action="reply" | "status_query" | "ignore", reason)`. The action is `status_query` when `is_status_query(text)` is true: after the mention of the agent is removed, the text contains `who works on what` as a case-insensitive substring.

## Transport-neutral identities
The core uses these names. The Slack mapping is in [contracts/transport.md](contracts/transport.md).

| Name | Meaning | Slack source |
|---|---|---|
| `sender_id` | Stable id of the sender. | `bot_id` for a bot message, else `user` |
| `sender_is_bot` | The sender is a bot. | `bot_id` is set |
| `sender_handle` | The handle that mentions the sender. | `user` |
| `card_owner_id` | The owner field of an agent card. | card `owner` |
| `owner` (config) | The owner of this agent. | a Slack user ID |

`is_owner(sender_id, owner)` (`core/router.py`) is true only when `owner` is not empty and equals `sender_id`. Every trust rule in specs 001 to 004 compares these neutral values.

## Message, Identity, Button (neutral types)
Fields: [contracts/transport.md](contracts/transport.md). They are frozen dataclasses in `src/pipe/core/contract.py`.

## ThreadTask
| Field | Type |
|---|---|
| `id` | str (= `thread_ts`) |
| `channel` | str |
| `sender` | str |
| `messages` | list[ThreadMessage(user, ts, text)] — this thread only (FR-002) |

## RuntimeInput / RuntimeOutput
See [contracts/runtime-contract.md](contracts/runtime-contract.md).

## SessionStatus
File: `~/.pipe/status/<session_id>.json`. Also the message `event_payload`.

| Field | Type | Rule |
|---|---|---|
| `v` | int | 1 |
| `session_id` | str | Key. |
| `who` | str | `agent_name`. |
| `repo` | str | Git top-level base name, else `cwd` base name. |
| `branch` | str | `""` if not a git repo. |
| `stage` | enum | `started`, `idle`, `stopped`. |
| `blocker` | str | `""` means none. Always `""` in 001 (known limit). |
| `started_at` | ISO-8601 UTC str | Set once. |
| `updated_at` | int (epoch seconds) | Set on each post and each `chat.update`. Moves forward only. Also written in the message metadata. |
| `channel`, `ts` | str | Local file only. Where the message lives. Not in the payload. |

All text fields of the payload (`who`, `repo`, `branch`, `blocker`) pass through `scrub` and `escape_mentions` before the post. The lock file `~/.pipe/status/<session_id>.lock` exists only while the hook posts the first message.

State transitions (`status.next_status(prev, event)`):

```text
(none) --SessionStart--> started
started|idle --Stop--> idle
started|idle --SessionEnd--> stopped
(none) --Stop--> idle            (lost start: create)
(none) --SessionEnd--> stopped   (lost start: create)
stopped --SessionStart (same id)--> started
any --SessionStart (same id)--> started (update in place, never a new message)
```

Invariant: one `session_id` maps to at most one message (SC-003).

## StatusSummary (output of "who works on what?")
`parse_status_messages(messages)` keeps only messages with `sender_is_bot` true and `event_type == "pipe.status.v1"`, with valid field types and a valid `stage`. It ignores all other posters. `recent(statuses, now)` keeps `SessionStatus` with `updated_at` (from the metadata, not the message `ts`) in the last 24 hours. `render_summary` gives one line per session: `who | repo | branch | stage | blocker`. Its output passes through `scrub`, and Slack mention syntax (`<!channel>`, `<!here>`, `<@U…>`) is escaped in all fields. Empty list gives "No sessions in the last 24 hours."

## ToolPolicy (type of the `claude` runtime adapter)
`ToolPolicy` is NOT a core type. It sits in `src/pipe/runtime_claude_tools.py`, with `tools_for`. The core never imports it. The core gives the runtime only `requester_is_owner` (`RuntimeInput.requester_is_owner`, contracts/runtime-contract.md).

| Field | Type |
|---|---|
| `tools` | list[str] |
| `allowed` | list[str] |
| `disallowed` | list[str] |
| `restricted` | bool (always `True`) |

`tools_for(requester_is_owner, owner_tools, deny_rules)` (pure, in `src/pipe/runtime_claude_tools.py`): `requester_is_owner` true gives `runtime.claude.owner_tools` (default `[Read, Grep, Glob]`), `disallowed = effective_deny_rules(deny_rules)` (always has `Bash(git push:*)`; the owner list only adds), and `restricted=True`. Otherwise it gives the empty tool set: `tools=[]`, `allowed=[]`, `disallowed=[]`, `restricted=True`. The empty tool set needs no deny rule. `build_cmd` (not `tools_for`) adds the path allow rules and `--add-dir` from `runtime.claude.repo_roots` for the owner (research.md D8). The runtime then gets `--tools ""` and reads nothing. The adapter computes `requester_is_owner = is_owner(sender_id, owner)`. If `owner` is missing or empty, the value is false for every sender (fail closed).
