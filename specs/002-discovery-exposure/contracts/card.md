# Contract: Agent card message (`pipe.card.v1`)

Source: design brief §5.3. Spec FR-007 to FR-013. One card per agent in `#pipe-agents`.

## Card message (Transport)

- Channel: `#pipe-agents` (config `agents_channel`, default `pipe-agents`).
- Author: the bot of the agent. Pinned with `pins.add`.
- `text`: a short readable list for people, built from the same sanitized card. Example lines: `coder-pavlo (laptop), owner U123` and one line per skill: `<id>: <description>`. It holds no URL, path, or token, and no mention syntax (Slack: `<@U...>`, `<!here>`): the adapter applies `escape_mentions` from 001 (no ping to the owner).
- `metadata`: `{ "event_type": "pipe.card.v1", "event_payload": <card> }`.
- Update: `Transport.update_message` of the same `ts` with the new `text` and the new `metadata` (Slack: `chat.update` needs both).

## `event_payload` (card)

```json
{
  "name": "coder-pavlo",
  "description": "Claude Code agent coder-pavlo",
  "owner": "<slack_user_id>",
  "bot_id": "<bot_id>",
  "bot_user_id": "<slack_user_id of the bot>",
  "kind": "agent",
  "mode": "laptop",
  "skills": [
    { "id": "skill:ponytail:ponytail-review", "name": "ponytail-review", "description": "...", "tags": ["skill", "ponytail", "review"] },
    { "id": "exec:lint-repo", "name": "Lint repo", "description": "...", "tags": ["exec", "lint"], "access": "read",
      "input_schema": { "type": "object", "required": ["repo"], "properties": { "repo": { "type": "string" } } },
      "output_schema": { "type": "object", "properties": { "findings": { "type": "integer" } } } }
  ],
  "hash": "<sha256 hex of the canonical JSON of skills>"
}
```

## Rules

1. `skills` holds exposed items only (FR-007). An `owner-only` item never appears. An item with role `group` (a plugin) and an item with role `listed_only` (a repo) never appear. The items of a group whose ID is in `exposed` appear one by one (FR-016). An item that is not `open` and that the owner exposed explicitly appears (FR-018).
2. No field holds an MCP URL, a token, a local path, or config content (FR-009, constitution). `sanitize_text` removes them. `validate_card` checks the result. A card with a violation is not posted.
3. `hash` = sha256 hex of `json.dumps(skills, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` encoded as UTF-8, with `skills` sorted by `id`.
4. The adapter updates the card only when `hash` differs from the stored hash (FR-011, FR-012). It never posts a second card while one exists.
5. An empty `skills` list is valid (spec edge case). `kind` is `agent` or `trigger`. A card of `kind: trigger` (spec 005) has `skills: []` and `mode: ci`. `validate_card` has no rule on `kind`, so it accepts such a card.
6. Readers (spec 003) trust this card only if the message has `sender_is_bot` true and `sender_id` equal to `payload.bot_id` (neutral names, spec 001 contracts/transport.md). 002 reads only its own card. Confirmed owner decision (2026-11-26): readers also require that the message `sender_handle` equals `bot_user_id` when `sender_handle` is present (assumption A8 of spec 003), and that the card with the lower `ts` keeps a duplicate `bot_user_id`. Spec 003 enforces both checks (`trusted_cards`, test task T007 of 003). 002 only publishes `bot_user_id`.
7. `bot_user_id` is the mention handle of the bot (Slack: the user ID of the bot), from `Transport.whoami` (Slack: `auth.test`). It is required. Other adapters mention this agent with `Transport.mention(bot_user_id)` (Slack: `<@bot_user_id>`). The core reads `bot_id` and `bot_user_id` as the opaque `agent_id` and `handle`. No `users:read` scope is needed (FR-021).
8. `skills[].id` is the stable capability ID (FR-022). It is the only discovery data that the core of specs 003 and 004 uses. `tags` hold the tags of the adapter (the type and the plugin name for the `claude` adapter) and then the declared tags: the owner tag map `tags` of this capability if it has an entry, else the frontmatter tags (FR-023, `resolve_tags`). The map wins. A tag `review` marks a review capability.
9. A declared capability (spec 002 FR-026) is a card entry like any other, when its ID is in `exposed`. The optional entry fields are `access`, `input_schema`, and `output_schema` (FR-029). They come from the config entry. The card never holds the runtime kind, the command, the URL, the token, the environment names, or the timeout. `validate_card` scans every string value of both schemas for a URL, a token-like string, and a path. Each schema is at most 2000 characters (canonical JSON). The `hash` covers these fields, so a schema change updates the card.

10. The wire field names `bot_id`, `bot_user_id`, and `owner` (and the task field `by`) stay as they are (owner decision of 2026-11-26, FR-032). The core reads them as the opaque `agent_id`, `handle`, and `card_owner_id`. An exposed `exec` capability always has an `input_schema` in its card entry (FR-031), because the config load refuses it without one.

## Pure interface (`src/pipe/core/card.py`, core; names no runtime term)

```python
def sanitize_text(text: str, limit: int = 200) -> str: ...
def skills_hash(skills: list[dict]) -> str: ...
def resolve_tags(cap: Capability, tag_map: dict[str, list[str]]) -> tuple[str, ...]: ...
def build_card(identity: Identity, caps: list[Capability], exposed: list[str], tag_map: dict[str, list[str]]) -> Card: ...   # raises CardError
def validate_card(card: Card) -> list[str]: ...        # violations; [] means safe
def decide_publish(new_hash: str, existing: CardState | None) -> Literal["post", "update", "none"]: ...
def pick_own_card(messages: list[dict], bot_id: str) -> CardState | None: ...
```

`Identity` = `agent_name`, `description`, `owner`, `bot_id`, `bot_user_id`. `Capability` is the core type (`src/pipe/core/capability.py`). The `claude` adapter builds it from a `ClaudeCapability` with `to_core` (`src/pipe/runtime_claude_exposure.py`). `tag_map` is the config key `tags`.

## Transport operations used (`ports.Transport`)

`update_message(channel, ts, text, metadata)`, `pin(channel, ts)`, `list_pins(channel) -> list[ts]`, `history(channel, limit)`, `send_dm(user_id, text)` (for the owner summary DM, [cli.md](cli.md)). The full port is in [../../001-adapter-core-status/contracts/transport.md](../../001-adapter-core-status/contracts/transport.md). `post_message` and `find_channel` exist from 001. 002 adds the optional `metadata` argument and an optional `thread_ts` (a card is a top-level post). `whoami` returns `bot_id` and `user_id` (the bot user ID; 001 stores it as `bot_user_id`).
