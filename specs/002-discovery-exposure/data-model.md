# Data Model: Discovery and Exposure

Core entities are frozen dataclasses in `src/pipe/core/`. They are agnostic: they name no plugin, skill, MCP server, or runtime tool (principle XI). Claude Code entities are frozen dataclasses in the `claude` runtime adapter (`src/pipe/runtime_claude_*.py`). The adapter classifies each item and gives the core one `Capability` per item. Persistent data is in `~/.pipe/` (JSON, atomic write, mode 0600), as in 001. No database. Spec entities: Capability, Exposure list, Tag map, Agent card, Card hash.

## Capability (core)
File: `src/pipe/core/capability.py`. Made by `to_core` of the adapter, then used by the pure core functions.

| Field | Type | Rule |
|---|---|---|
| `id` | str | `<type>:<qualified name>` (research.md D1). Unique after `assign_ids`. Stable across restarts and discovery order. The core uses it as `capability_id`. The core treats it as an opaque string. |
| `name` | str | Display name. Non-empty. |
| `description` | str | Raw text. Empty string if missing. `sanitize_text` runs in `build_card`. |
| `role` | enum | `item` (can be a card entry), `group` (a container: exposing its ID exposes its items; never a card entry), or `listed_only` (shown to the owner, never exposable, never a card entry). |
| `open` | bool | The class from the adapter: `true` means the adapter proved the item safe. It matters for `role` `item` only. |
| `group` | str? | `id` of the `group` item that holds this item, or `None`. |
| `tags` | tuple[str] | Tags that the adapter adds (for the `claude` adapter: the type and the plugin name). |
| `declared_tags` | tuple[str] | Tags that the item declares itself (for the `claude` adapter: the frontmatter `tags`), after `sanitize_tags`. The tag map replaces them (FR-023). |
| `runtime` | str | Opaque name of the runtime adapter that runs this capability: `claude` (default), `exec`, or `http`. The core uses it only to pick the adapter (spec 003). It never enters the card. |
| `access` | str? | `read`, `write`, or `None`. `None` means the runtime adapter sets the limit (a `claude` item). A declared capability has `read` in this version (FR-028). It enters the card when it is not `None`. |
| `input_schema`, `output_schema` | dict? | Optional schema (JSON Schema subset, research.md D20). `None` when missing. They enter the card. |
| `classified` | bool | Default `true`. `false` for a declared capability: no adapter classified it, so the credential notice does not apply (FR-027). |

Validation: `id` and `name` are non-empty. The pure function `sanitize_tags(raw) -> tuple[str, ...]` keeps a tag when it is lower case, matches `[a-z0-9-]`, and has at most 32 characters. It keeps at most 8 tags and drops duplicates. `Notice(kind, id, text)` is also in this file.

## ClaudeCapability (`claude` adapter)
File: `src/pipe/runtime_claude_capability.py`. Built by `src/pipe/runtime_claude_discovery.py` (I/O).

| Field | Type | Rule |
|---|---|---|
| `id` | str | Same rule as the core `id` (research.md D1). |
| `type` | enum | `skill`, `command`, `mcp`, `plugin`, `repo`. |
| `name` | str | Skill: frontmatter `name`, else directory name. Command: file name without `.md`. MCP: server name. Plugin: `plugin.json` `name`. Repo: directory base name. |
| `description` | str | Frontmatter `description` (text may be folded). Empty string if missing. |
| `declared_tags` | tuple[str] | The frontmatter `tags` after `sanitize_tags`. Empty when the key is missing (research.md D9). |
| `plugin` | str? | Plugin name (the part before `@`), or `None` for personal items. |
| `plugin_id` | str? | ID of the plugin item (`plugin:<name>`, with the collision suffix if any), or `None` for personal items. |
| `allowed_tools` | tuple[str]? | From frontmatter `allowed-tools` (skill, command). `None` when the key is missing. |
| `signals` | tuple[str] | Credential signals found in the frontmatter and the body (research.md D3). Computed by the pure function `find_signals(text)`. Names of signals only, not text. |
| `source` | str | INTERNAL. Local path of the skill directory, command file, or plugin. Never in the card, the notices, or Slack. Never printed by `pipe capabilities`. |
| `source_key` | str | INTERNAL. Input of the collision suffix. Equals `source`. |

Validation: `id`, `type`, `name` are non-empty. A capability with an unreadable `SKILL.md` or bad frontmatter is skipped, and a notice names its `id` or directory base name (no path).

`to_core(cap) -> Capability` (in `src/pipe/runtime_claude_exposure.py`) maps a `ClaudeCapability`:

```text
type skill, command  -> role item, open = (classify(cap) == "open"), group = plugin_id, tags = (type, plugin name)
type mcp             -> role item, open = false, group = None, tags = (type,)
type plugin          -> role group, open = false
type repo            -> role listed_only, open = false
declared_tags        -> declared_tags
every claude item    -> runtime = claude, access = None, classified = true, no schema
```

## Declared capability (config)
Config key `capabilities` in `~/.pipe/config.yaml` (brief §5.4). Default `[]`. Each entry is a map. `validate_config` checks it. The pure function `declared_caps(entries) -> list[Capability]` (`src/pipe/declared.py`, not a core module) builds the core `Capability` values.

| Key | Applies to | Rule |
|---|---|---|
| `id` | both | Required. `^[a-z0-9][a-z0-9._-]{0,63}$`. The capability ID is `<runtime>:<id>`. Two entries with the same runtime and `id` are an error. |
| `name` | both | Required. 1 to 80 characters. |
| `description` | both | Required. At most 200 characters (the card cuts it, `sanitize_text`). |
| `tags` | both | Optional. Same rule as `sanitize_tags` (at most 8, lower case `[a-z0-9-]`, at most 32 characters). These are `declared_tags`. The tag map (FR-023) replaces them. |
| `access` | both | Required. `read`. `write` is an error (confirmed 2026-11-26, constitution 1.3.0). |
| `runtime` | both | Required. `exec` or `http`. |
| `command` | `exec` | Required. A non-empty list of strings. The first item is an absolute path (`~` expanded). A string, or a list item that is not a string, is an error. No shell is used. |
| `env_allow` | `exec` | Optional. A list of variable names `^[A-Za-z_][A-Za-z0-9_]*$`. Default `[]`. |
| `url` | `http` | Required. `https://` (or `http://` for `localhost` and `127.0.0.1`; confirmed 2026-11-26). No user name, no password. |
| `token` | `http` | Optional. `keychain:<service>`. A plain token is an error. |
| `timeout_s` | both | Optional. An integer from 1 to 3600. Default: `step_timeout_min` of the config. |
| `input_schema`, `output_schema` | both | Optional, with one rule: an `exec` entry whose `<runtime>:<id>` is in `exposed` MUST have an `input_schema` (FR-031). The config check fails with `capability exec:<id> is exposed and has no input_schema`. Subset check (`core/schema.py`): errors name the entry `id`. No string value holds a URL, a path, or a token-like string. |

Any other key is an error. `declared_caps` maps an entry to the core `Capability`:

```text
id            = "<runtime>:<id>"
role          = item          open = false          classified = false      group = None
tags          = (<runtime>,)  declared_tags = sanitize_tags(entry.tags)
runtime       = entry.runtime  access = entry.access
input_schema, output_schema   = copied
```

The fields `command`, `env_allow`, `url`, `token`, and `timeout_s` stay in the config. The `exec` and `http` adapters (spec 003) read them. They never enter a core type, a card, a notice, or a log line.

## ExposureState
Derived value, not stored.

| Function | Home | Result |
|---|---|---|
| `classify(cap)` | `claude` adapter (`runtime_claude_exposure.py`) | `owner-only` or `open` for a `ClaudeCapability` (research.md D3). The safe tool set and the credential signs are here. |
| `state_of(cap, exposed)` | core (`core/exposure.py`) | `exposed` or `owner-only` for a core `Capability` (research.md D4). |
| `exposed_by(cap, exposed)` | core | `owner` (item ID or `group` ID in `exposed`), `clean` (only `open`), or `None`. |

State rules (summary):

```text
role listed_only                  -> owner-only   (listed only; never in the card)
role group                        -> exposed if id in exposed, else owner-only (never in the card)
role item, id or group in exposed -> exposed (by owner, even if not open)
role item, open                   -> exposed (by clean rule; no owner action)
role item, not open               -> owner-only
```

There is no `hidden:` key. A clean item leaves the card when it stops being `open`, unless `exposed_by` is `owner` (Q4).

## Exposure list
Config key `exposed` in `~/.pipe/config.yaml`. List of capability IDs. Default `[]`. An ID can be a skill, command, MCP server, or plugin ID. A plugin ID exposes all skills of that plugin (FR-016). Only the owner edits the file (principle II, FR-006). Items that do not match a discovered capability, or that have role `listed_only`, give a notice and are ignored (FR-014, FR-017).

## Tag map
Config key `tags` in `~/.pipe/config.yaml` (brief §5.4). A map from a capability ID to a list of tags. Default `{}`. In the config, a tag that is not lower case `[a-z0-9-]` with at most 32 characters, or a list with more than 8 tags, is a config error (the owner fixes the file). An entry replaces `declared_tags` of that capability. The entry does not replace `tags` of the adapter. An empty list is valid: it removes the declared tags. The pure function `resolve_tags(cap, tag_map) -> tuple[str, ...]` in `core/card.py` returns `cap.tags` plus the list of the map (if the ID has an entry) or `cap.declared_tags` (if not). Only the owner edits the map (principle II).

## Notice
`exposure_notices(caps, exposed, tag_map)` (core) returns a list of `Notice(kind, id, text)`.

| `kind` | When |
|---|---|
| `unknown_id` | An ID in `exposed` matches no discovered capability. |
| `not_exposable` | An ID in `exposed` has role `listed_only`. |
| `credential_exposed` | A `role` `item` with `classified` true is exposed by the owner (by its ID or by its `group` ID) and is not `open`. A declared capability never gives this notice (FR-027). |
| `unknown_tag_id` | An ID in `tag_map` matches no discovered capability. |
| `skipped` | A capability was skipped (bad frontmatter, or name collision in the generated plugin). The adapter creates this notice. |

`text` holds the `id` and a fixed sentence. It holds no path, URL, or value from a file.

## Agent card
File: `src/pipe/core/card.py` (core, agnostic). Shape: design brief §5.3. Message `metadata`: `event_type = "pipe.card.v1"`, `event_payload` = the card.

| Field | Type | Rule |
|---|---|---|
| `name` | str | Config `agent_name`. |
| `description` | str | Config `description`, default `Claude Code agent <agent_name>`. Sanitized. |
| `owner` | str | Config `owner` (the `card_owner_id`; a Slack user ID in the Slack adapter). Required. |
| `bot_id` | str | From `auth.test`. Required. |
| `bot_user_id` | str | The mention handle of the bot, from `Transport.whoami` (Slack: `auth.test` `user_id`). Required. The core checks only a neutral form (`^[A-Za-z0-9._:-]{2,64}$`). The transport checks its own form (Slack: `U` or `W` plus upper-case letters and digits). Other adapters mention this agent with `Transport.mention(bot_user_id)`. |
| `kind` | str | `agent` (the card kind; the `trigger` kind is for spec 005). |
| `mode` | str | `laptop`. |
| `skills` | list[CardSkill] | Exposed items of role `item`, sorted by `id`. May be empty. |
| `hash` | str | sha256 hex of the canonical JSON of `skills` (research.md D9). |

CardSkill: `id` (str), `name` (str, sanitized, max 200), `description` (str, sanitized, max 200), `tags` (list[str]: `resolve_tags`, in order, no duplicates), and the optional `access` (`read`, when not `None`), `input_schema`, and `output_schema` (copied when not `None`). The entry never holds `runtime`, `command`, `url`, `token`, `env_allow`, or `timeout_s` (FR-029).

Invariants (tested):
- No field holds a URL, a token-like string, or a path-like string (`validate_card` returns `[]`). The scan covers every string value in `input_schema` and `output_schema`.
- The same input gives the same `hash` (stable order and encoding).
- The order of discovery does not change the `hash`.
- A change of any `skills` field changes the `hash`. A change of the tag map that changes the tags of an exposed item changes the `hash`.
- The `hash` does not depend on `name`, `description`, or `owner` of the card.

## CardState (local)
File: `~/.pipe/state.json`, keys added by 002:

| Key | Type | Rule |
|---|---|---|
| `bot_id` | str | From `auth.test`. |
| `bot_user_id` | str | From `auth.test` (`user_id`). Written by 001. 002 reads it for the card. |
| `agents_channel_id` | str | Cached from `conversations.list`. |
| `card` | `{channel, ts, hash}` | Where the card lives and its last published hash. Written after a successful post or update. |
| `summary_hash` | str | sha256 hex of the last owner summary DM that was sent. Written only after a successful post (FR-020). |

State transitions (`decide_publish(new_hash, existing)`):

```text
no existing card            --> post   (then pins.add)
existing.hash != new_hash   --> update (chat.update, same ts)
existing.hash == new_hash   --> none   (no transport write except pin repair)
update fails: message_not_found --> post (then pins.add)
```

Invariant: one agent has at most one card in `#pipe-agents` (SC-004). `find_own_card` recovers the `ts` from the transport when the key `card` is missing.

## Summary
File: `src/pipe/core/summary.py` (core). Result of `build_summary(caps, exposed, notices)` (FR-019). `caps` are core `Capability` values.

| Field | Type | Rule |
|---|---|---|
| `text` | str | One count line (`N exposed, N owner-only, N skipped`), then one line per notice. Names, IDs, and counts only. No path, URL, or token. |
| `hash` | str | sha256 hex of `text`. Same input gives the same hash. The order of discovery does not change it. |

`decide_dm(new_hash, last_hash)` returns `send` when `last_hash` is `None` or differs, else `none` (FR-020).

## LoadSet
File: `src/pipe/runtime_claude_loadset.py` (part of the `claude` runtime adapter, pure). Result of `load_set(caps, exposed, capability_ids)`. `caps` are `ClaudeCapability` values. `capability_ids` is the list of IDs that the core sends. The function calls `to_core` and the core `state_of`. Input to the runtime builder (contracts/runtime-load.md).

| Field | Type | Rule |
|---|---|---|
| `skills` | tuple[(link_name, source_dir)] | Exposed `skill` items. `link_name` is the directory name in the generated plugin. |
| `commands` | tuple[(link_name, source_file)] | Exposed `command` items. |
| `mcp` | tuple[str] | Server names of exposed `mcp` items. |
| `skipped` | tuple[Notice] | Items skipped for a `link_name` collision. |

Derived: `allowed_rules` = `Skill(pipe-exposed:<link_name>)` for each skill and command, and `mcp__<server>` for each server. `needs_skill_tool` = true when `skills` or `commands` is not empty.

Rules: only items whose ID is in `capability_ids`, whose state is `exposed` now, and whose type is `skill`, `command`, or `mcp` enter the set. An ID with no match, or not exposed, is skipped with a notice (second check at run time). (the skills of an exposed plugin enter one by one; a `plugin` or `repo` item never enters). The order is sorted by `id`. A set built from no exposed item is empty (no flag is added). 002 builds the set in tests only. No 002 run path uses it (Q2).
