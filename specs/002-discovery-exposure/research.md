# Research: Discovery and Exposure

All "NEEDS CLARIFICATION" items are resolved. The five design questions are settled in [plan.md](plan.md) ("Design decisions"). Source of decisions: `docs/design-brief.md` §5.3, §5.4, §8, §9 (M1), §12. This file does not change them. Spec 001 modules are reused: see [../001-adapter-core-status/research.md](../001-adapter-core-status/research.md).

## Checked on this machine (2026-11-25)

Tool versions and flags:

- `claude --version` shows `2.1.325 (Claude Code)`.
- `claude --help` shows these flags (checked): `--plugin-dir <path>` (load a plugin from a directory or .zip for this session only; repeatable), `--mcp-config <configs...>`, `--strict-mcp-config`, `--settings <file-or-json>`, `--setting-sources`, `--add-dir`, `--tools`, `--allowedTools`, `--disallowedTools`, `--permission-mode`, `--restricted`, `--bare`, `--safe-mode`, `--disable-slash-commands`.
- `--restricted` help text: "ignores user, project and local settings files (managed settings and `--settings` still apply; add `--strict-mcp-config` to skip MCP servers too)". It also confines file tools to the working directories.
- `--bare` skips OAuth and Keychain reads. It is not usable here (the adapter uses the owner's login). Rejected.

Real runs with the real `claude` (probe plugin and probe MCP config in the scratchpad; no secret used; each run capped with `--max-budget-usd 0.3`):

| # | Command (shortened) | Result |
|---|---|---|
| P1 | `--restricted --strict-mcp-config`, ask for an installed plugin skill (`superpowers:brainstorming`) | NO. Installed plugins are not loaded. |
| P2 | same, ask for a personal skill (`project-context` from `~/.claude/skills`) | NO. Personal skills are not loaded. |
| P3 | `--restricted --plugin-dir <probe plugin> --tools Skill --allowedTools "Skill(pipeprobe:hello)"` | The probe skill ran and returned its text. `--plugin-dir` works under `--restricted`. |
| P4 | same with `--allowedTools "Skill(pipeprobe:other)"` | Denied (`dontAsk` mode). A per-skill allow rule limits which skill can run. |
| P5 | same with `--tools ""` | The Skill tool is not available. `--tools ""` removes it. |
| P6 | plugin that has a `SessionStart` hook, loaded with `--plugin-dir` under `--restricted` | The hook ran. Plugin hooks are NOT disabled by `--restricted`. |
| P7 | same with `--settings '{"disableAllHooks":true}'` | The hook did not run. `--settings` is honored under `--restricted`. |
| P8 | generated plugin `pipe-exposed` (`.claude-plugin/plugin.json`, `skills/<name>` as symlinks to skill directories, `commands/<name>.md` copied) loaded with `--plugin-dir` | Skills and the command appear as `pipe-exposed:<name>`. A symlinked skill runs with `--allowedTools "Skill(pipe-exposed:hello)"`. |
| P9 | `--restricted --strict-mcp-config --mcp-config <file with one stdio server> --tools ""` | Exactly that server's tools appear (`mcp__<server>__<tool>`). Without `--mcp-config`, no `mcp__` tool exists. MCP tools do not need the `--tools` list. |

Not checked by a real run: the permission to call an MCP tool (the plan assumes `--allowedTools "mcp__<server>"` is needed under `dontAsk`); the MCP server of a plugin that is loaded by `--plugin-dir` (the generated plugin has none, so the case does not occur); two exposed skills with the same directory name (see D6).

Discovery sources (file shapes, names only; no value copied):

- `~/.claude/plugins/installed_plugins.json`: JSON `{ "version": 2, "plugins": { "<plugin>@<marketplace>": [ { scope, installPath, version, installedAt, lastUpdated, gitCommitSha } ] } }`. 19 entries on this machine. `installPath` is an absolute local path (internal only).
- `~/.claude/settings.json`: key `enabledPlugins` is `{ "<plugin>@<marketplace>": true|false }`. Discovery reads this key only. It reads no other key.
- Plugin directory (under `installPath`): `.claude-plugin/plugin.json` with `name`, `version`, `description` (and sometimes `mcpServers`, `hooks`); `skills/<dir>/SKILL.md`; `commands/<file>.md`; `agents/<file>.md`; `hooks/`.
- `SKILL.md` format: YAML frontmatter between `---` lines with `name`, `description` (plain or folded `>` text), optional `allowed-tools`, `argument-hint`; then the Markdown body.
- Command format: `commands/<name>.md` with YAML frontmatter (`description`, optional `argument-hint`, `allowed-tools`, `version`, `tags`) and a body. The name comes from the file name.
- `~/.claude/skills/<dir>/SKILL.md`: personal skills. Some entries are symlinks to other directories. A `synced` directory holds a `manifest.json` and a skills set from a connector. Discovery treats a directory with a `SKILL.md` as a skill, and ignores `synced`.
- `~/.claude/commands/*.md`: personal commands, same format as plugin commands.
- `~/.claude.json`: key `mcpServers` is `{ "<name>": { type, url | command, args, env, headers } }`. 14 servers on this machine. Values can hold URLs and secret headers. Discovery reads the names. Only the run-time loader reads a whole entry (D7). `claude mcp list` is NOT used: it opens network connections to check health and prints URLs and commands.
- Plugin MCP servers: `plugin.json` key `mcpServers` is a string path to a JSON file or an inline object. Some plugins have a `.mcp.json`. On this machine one plugin (postman) uses the string form.
- Claude.ai connectors (shown by `claude mcp list` as `claude.ai ...`) are not in a local file. Discovery does not find them. See D5.
- Repos: directories under `runtime.claude.repo_roots` that contain `.git`.

## Decisions

### D1. Capability ID
- Decision: `<type>:<qualified name>`. The type is a word of the `claude` adapter. The core treats the whole ID as an opaque string. Types: `skill`, `command`, `mcp`, `plugin`, `repo`. A plugin item uses `<plugin>:<name>` (the plugin name is the part before `@marketplace`). A personal item uses `<name>`. Examples: `skill:superpowers:brainstorming`, `skill:project-context`, `command:lang`, `mcp:gitlab`, `mcp:postman:postman`, `plugin:ponytail`, `repo:pipe.ai`. If two items get the same ID (same plugin from two marketplaces, two repos with the same base name), each gets the suffix `#<6 hex of sha256 of its source key>`. The source key stays internal.
- The `exposed` config list holds these IDs. The card `skills[].id` uses the same ID. This ID is the `capability_id` that the core of specs 003 and 004 uses. It is stable: it comes from the type, the plugin name, and the item name only. A restart, a change of discovery order, or a change of the description does not change it. Only a rename of the item, or a name collision (suffix), changes it. The core never reads a path, a type, or a discovery source.
- Rationale: the ID is stable, unique, readable, and holds no path. This covers the edge case "same skill name in two plugins". It matches how Claude Code names plugin skills (`plugin:skill`).
- Alternatives: plain names like `review-mr` (brief §5.4 example). Rejected: collide across plugins. UUIDs. Rejected: the owner cannot read them in the config file.

### D2. Which capabilities are in scope, and the card entries
- Decision: discovery reports five types (FR-001). The card lists only `skill`, `command`, and `mcp` items that are exposed, as `skills[]` entries with a tag for the type (design brief §5.3: "Only exposed capabilities go into `skills`"). A `plugin` item is never a card entry. An `exposed` entry with a plugin ID exposes all skills of that plugin (Q1 = b, FR-016). Each of those skills still goes through `classify`. A `repo` item is listed to the owner only. It is always `owner-only` and never in the card (FR-017). Repo work belongs to spec 004.
- Rationale: a plugin is a container of skills. One ID is a short way to expose all of them. A repo name alone gives no capability. Repo work is delegation (spec 004).

### D3. Classification rule (pure function `classify`, `claude` adapter)
- Decision: `classify` is part of the `claude` adapter (`src/pipe/runtime_claude_exposure.py`). The safe tool set and the credential signs are Claude Code terms. The result is `owner-only` or `open`. `to_core` gives it to the core as the field `open` (D17).
  1. `mcp`, `plugin`, `repo`: always `owner-only` by `classify`. (A plugin ID in `exposed` still exposes the skills of the plugin, see D4.)
  2. `skill` and `command`: `open` only when BOTH hold: (a) the frontmatter has a non-empty `allowed-tools` list and every item is in the read-only safe set `Read`, `Grep`, `Glob` (`Edit`, `Write`, and `NotebookEdit` make it `owner-only`); (b) no credential signal appears in the frontmatter or the body. Otherwise `owner-only`.
  3. Credential signals (case-insensitive substring or regex): `mcp__`, a URL (`http://`, `https://`), the words `token`, `api key`, `api_key`, `secret`, `password`, `credential`, `oauth`, `login`, `.env`, an environment variable name that ends in `_TOKEN`, `_KEY`, or `_SECRET`, and the commands `curl`, `wget`, `ssh`, `scp`, `gh `, `glab`, `kubectl`, `aws `, `gcloud`, `docker`, `git push`, `psql`, `mysql`.
- Rationale: the spec Assumptions say "when unsure, treat the capability as `owner-only`". A skill with no declared `allowed-tools` can call any tool, so the rule cannot prove it is safe. A skill that is not proven safe stays `owner-only`. The signal list adds a second check for declared lists that look safe. The owner can still expose any `owner-only` item by listing it, or its plugin ID, in `exposed` (FR-005). A clean skill is exposed with no owner action (FR-015, Q3 = a). There is no `hidden:` key. Add `hidden:` when an owner wants to hide a clean skill (YAGNI).
- Consequence: most skills on this machine are `owner-only`, because few declare `allowed-tools`. The card is short at first. The owner lists more IDs in `exposed`. The consequence is intended.
- Alternatives: signal scan only (treat as `open` when no signal is found). Rejected: a false negative leaks the credentials of the owner (principle III). An LLM judge. Rejected: principle VII needs a pure function without an LLM.

### D4. Exposure state (pure function `state_of`, core)
- Decision: `state_of(cap, exposed)` works on the core `Capability`. It is `exposed` when `cap.id` is in `exposed`, or when `cap.group` is in `exposed` (an item of an exposed plugin), or when `cap.role` is `item` and `cap.open` is true. Else `owner-only`. Role `listed_only` (a repo) is always `owner-only`. A `group` item (a plugin) shows `exposed` when its ID is in `exposed` (its items are exposed), but it is never a card entry. The pure function `exposed_by(cap, exposed)` returns `owner` (the item ID or its `group` ID is in `exposed`), `clean` (only the clean rule), or `None`. Only the owner can edit `exposed` (the file `~/.pipe/config.yaml` is local, principle II).
- Rationale: design brief M1 acceptance: "A new skill appears → the card updates within one adapter start" (a new clean skill needs no owner action). Brief M1 and the spec: "Capabilities that use the owner's credentials are hidden by default." Both hold.
- Edge cases:
  - A capability changes from `open` to credential-backed (spec edge case, Q4 = a, FR-018): `classify` returns `owner-only` at the next start, so `open` is false. If `exposed_by` is `clean`, it leaves the card at that start. If `exposed_by` is `owner` (its ID or its plugin ID is in `exposed`), it stays exposed (explicit choice) and the notice says "exposed by owner choice; credential-backed" (D8).
  - A skill of an exposed plugin is credential-backed (Q1 = b, FR-016): it is exposed and the same notice appears.
  - The owner lists an ID that does not exist (FR-014): ignored for the card, and a notice names it.
  - The owner lists an ID with role `listed_only` (a repo): ignored for the card, and a notice says a repo cannot be exposed (FR-017).

### D5. Discovery of MCP servers
- Decision: read these sources, names only for the list: the key `mcpServers` of `~/.claude.json` (user scope), and the `mcpServers` of each enabled plugin (`plugin.json` inline object, string path, or `.mcp.json`). Project-scope servers (`.mcp.json` in a repo, and `projects.<path>.mcpServers`) and claude.ai connectors are not discovered. Ceiling: the owner sees a shorter list than `claude mcp list` shows. Add them later if the owner asks.
- Rationale: `claude mcp list` prints URLs and commands, runs health checks over the network, and takes seconds. Reading JSON is fast, offline, and shows names without values.

### D6. How exposed capabilities reach a `--restricted` child (design brief §12)
- Decision: for each run that needs exposed capabilities, the adapter builds one generated plugin and passes it explicitly:
  1. Directory `~/.pipe/run/<run_id>/exposed-plugin/` (mode 0700) with `.claude-plugin/plugin.json` (`{"name":"pipe-exposed","version":"0.0.0","description":"generated"}`), `skills/<name>` (a symlink to the source skill directory) for each exposed `skill`, and `commands/<name>.md` (a copy of the source file) for each exposed `command`.
  2. Flag `--plugin-dir ~/.pipe/run/<run_id>/exposed-plugin`.
  3. Flag `--allowedTools "Skill(pipe-exposed:<name>)"` for each exposed skill or command, and `Skill` added to `--tools` (P5: `--tools ""` removes the Skill tool).
  4. For MCP: the adapter writes `~/.pipe/run/<run_id>/mcp.json` (mode 0600) that holds only the exposed servers (full entries copied from the source config, in the file only), and passes `--mcp-config <that file>` together with the existing `--strict-mcp-config`, plus `--allowedTools "mcp__<server>"` for each exposed server.
  5. `--restricted` stays on every run. File confinement is unchanged (001 D8). The caller that prepared the load removes `~/.pipe/run/<run_id>/` after the run (`cleanup`, also after a failure).
- Verified by real runs: P3 to P9 above (`--restricted` with `--plugin-dir`, per-skill allow rules, `--tools ""` effect, symlinked skills, `--mcp-config` with `--strict-mcp-config`).
- Rationale: one mechanism for plugin skills, personal skills, and commands. Only exposed items load. Other skills of the same plugin do not load. A generated plugin has no hooks (P6 showed that plugin hooks run in a restricted child; a generated plugin avoids this) and no MCP servers of its own. The adapter never edits the owner's `settings.json` and never uses `--settings` to turn on plugins (installed plugins load whole, with their hooks and MCP).
- Fallback if a skill breaks because it needs files outside its directory (for example a script under `${CLAUDE_PLUGIN_ROOT}`): load the whole plugin with `--plugin-dir <installPath>` and add `--settings '{"disableAllHooks":true}'` (P7). Not planned now.
- Alternatives: `--settings` with `enabledPlugins` (does not select single skills; loads hooks and MCP of the plugin). `--setting-sources user` (drops `--restricted` confinement of settings; loads the owner's hooks and all plugins). Drop `--restricted` (loses file confinement; the brief says keep it). `--bare` (cannot use the owner login).
- Scope (Q2 = a): 002 builds and tests the generated plugin and the flags (pure `load_set`, `runtime_claude_load.py`, `build_cmd(..., prepared=...)`). 002 does not load anything into a run: no 002 code calls `prepare`, and the adapter passes `prepared=None`. Specs 003 and 004 pass capability IDs and an access level to the `claude` adapter. The adapter builds the load set from the IDs, calls `prepare`, and calls `cleanup`.
- Ceiling: a skill that reads sibling files outside its own directory can fail. Two exposed skills with the same directory name collide inside `pipe-exposed`. The second one is skipped and a notice names it.

### D7. MCP config copy
- Decision: `~/.pipe/run/<run_id>/mcp.json` is the only place where a full server entry is written. The file has mode 0600 and is deleted after the run. No log line, no card, no Slack text holds an entry. Tests use fake entries with fake secrets and assert that the card and the notices never contain them.
- Rationale: the child needs the real URL and headers to connect. The file is local and short-lived.

### D8. Owner view (FR-002) and notices (FR-014)
- Decision: `pipe capabilities` prints one line per capability: `<state>  <type>  <id>  <name>`. Sections: counts, then the notices. The adapter prints the same lines to `~/.pipe/logs/adapter.log` at start. Notices come from the pure function `exposure_notices(caps, exposed)`: unknown IDs, repo IDs in `exposed`, exposed items that are credential-backed (by item ID or by plugin ID), and skipped name collisions. The text never holds a path, URL, or token. The screen shows names only. The owner also gets one Slack DM at start (D15).
- Rationale: no new server (principle I). The owner already reads the log and runs `pipe` commands. The DM makes a change visible without a command.

### D9. Card build, hash, and checks (pure functions)
- Decision: `build_card(identity, caps, exposed, tag_map)` (core, with core `Capability` values) returns the card of design brief §5.3: `name` (`agent_name`), `description` (config key `description`, default `Claude Code agent <agent_name>`), `owner`, `bot_id`, `bot_user_id`, `kind: "agent"` (the card kind), `mode: "laptop"`, `skills[]` (`id`, `name`, `description`, `tags`), `hash`. Rules:
  - Entries: exposed items of role `item`, sorted by `id`.
  - `bot_user_id` comes from `auth.test` (`user_id`; 001 stores it as `bot_user_id` in `state.json`). It is the Slack user ID of the bot. Other adapters mention this agent as `<@bot_user_id>`. No `users:read` scope is needed. Empty `bot_user_id`: `build_card` raises `CardError`.
  - `tags` = `resolve_tags(cap, tag_map)` (D18): the adapter tags (`cap.tags`: for the `claude` adapter the type and the plugin name), then the owner tag map list for this ID if the map has an entry, else the declared tags (`cap.declared_tags`: the frontmatter `tags`). Each tag passes `sanitize_tags` (lower case, `[a-z0-9-]`, at most 32 characters, at most 8 tags). The tag `review` marks a review capability (design brief §6).
  - Each text field passes `sanitize_text`: remove URLs and path-like strings (replace with `[removed]`), apply 001 `scrub` (tokens), collapse spaces, cut to 200 characters. This covers the edge case "a repo path or an MCP URL appears in the description".
  - `hash` = hex sha256 of the canonical JSON (`sort_keys`, separators `,` and `:`, UTF-8) of the `skills` list.
  - `validate_card(card)` returns a list of violations: any URL, token-like string, or path-like string in any field. A non-empty list blocks the publish and gives a notice. The check is a second wall after `sanitize_text` (FR-009, SC-003).
  - Empty `owner` or empty `bot_id`: `build_card` raises `CardError`; no card is posted (trust needs the owner; the owner check of 001 warns the same way).
  - No exposed item: the card still exists with `skills: []` (edge case).
- The message text for people is a short readable list made from the same card (sanitized). `metadata` is `event_type = "pipe.card.v1"` with the card as `event_payload`.
- Known limit: the hash covers the skills list only (brief §5.3, FR-010). A change of `description`, `owner`, or `bot_user_id` alone does not update the card. The owner can add a skill change or remove the card message (the next start posts a new one). This is the cost of FR-012.

### D10. Publish flow (`card_sync.sync_card`)
- Decision: at start, after 001 start-up (`auth.test`, channel lookup) and before the catch-up pass:
  1. Run discovery, `state_of`, `build_card`, `validate_card`. On `CardError` or violations: log a notice, skip the card, continue the adapter (a card problem never stops mention handling).
  2. Find the channel `#pipe-agents` (config `agents_channel`, default `pipe-agents`) with `Transport.find_channel`. Cache its ID in `state.json` (`agents_channel_id`).
  3. Read `state.json` key `card` = `{channel, ts, hash}`. If the key is missing, call `find_own_card`: read `conversations.history` of the channel with `include_all_metadata`, and use the pure `pick_own_card(messages, bot_id)` (newest message with `bot_id` = own and `event_type = "pipe.card.v1"`). This is the recovery path when `state.json` is lost (SC-004).
  4. Pure `decide_publish(new_hash, existing)` returns `post` (no card), `update` (hash differs), or `none` (hash equal). `post`: `chat.postMessage` with `metadata`, then `pins.add`; save `card`. `update`: `chat.update` with the new text and `metadata` (Slack needs the metadata again on update); save the hash. `none`: no change (FR-012).
  5. Always call `pins.list` once. If the card is not pinned, call `pins.add` (edge case: unpinned by a person). If `chat.update` fails with `message_not_found` (deleted by a person), post a new card and pin it. A person who deleted the card gets a new card at the next start.
- Rationale: same `chat.update` pattern as the 001 status hook. One card per agent. Slack is the state (principle I).

### D11. Config keys
- New optional keys in `~/.pipe/config.yaml`: `capabilities` (declared capabilities, D19), `description` (str, default `Claude Code agent <agent_name>`, max 200 characters), `agents_channel` (str, default `pipe-agents`), `tags` (map from a capability ID to a list of tags, default `{}`; D18). The key `exposed` (list of IDs, default `[]`) was reserved in 001 ("accepted and ignored"). 002 validates it: a list of non-empty strings. A missing key means `[]`. A wrong type is an error.
- New keys in `~/.pipe/state.json`: `bot_id` (from `auth.test`), `agents_channel_id`, `card` (`{channel, ts, hash}`), `summary_hash` (sha256 hex of the last summary DM that was sent). 001 `state.py` already keeps other keys when it writes one key.

### D12. Slack scopes and limits
- Add bot scopes: `pins:write`, `pins:read`, `im:write` (to open the DM with the owner; Q5). `chat:write` is already in the 001 scope list (001 D5), so it is not added again. Existing scopes cover `chat:write`, `chat:update` (part of `chat:write`), `channels:history`, `channels:read`, and `metadata.message:read` (001 D5). For a private channel `#pipe-agents`, add `groups:history`, `groups:read`.
- `auth.test` returns `bot_id` (B...) and `user_id`. 001 stores `bot_user_id`. 002 stores `bot_id` too. 002 puts both in the card. 002 adds no `users:read` scope: the card carries `bot_user_id`, so other adapters need no `bots.info` or `users.info` call (owner decision Q7 = b of spec 003).

### D13. Testing
- `pytest`. Unit tests for every new pure module are written first (principle VII): `capability`, `exposure`, `card`, `summary` (in `core/`), and `runtime_claude_capability`, `runtime_claude_exposure`, `runtime_claude_loadset` (in the `claude` adapter). Fakes: `FakeTransport` (from 001) gets `update_message`, `pin`, `list_pins`, and history with metadata. The helper `build_claude_tree(tmp_path)` in `tests/fakes.py` builds a temporary directory tree (plugins, skills, commands, `~/.claude.json`) with fake values.
- Integration tests (no real Slack, no real Claude): start with new skill → one card posted and pinned; restart → no change; add a skill → same card updated; MCP server → not in card; expose it → in card; remove → leaves; unknown ID → notice; deleted card → new card; unpinned → re-pinned; lost `state.json` → card found, no second card; 10 restarts → one card (SC-004); card scan finds no URL, token, or path (SC-003); plugin ID in `exposed` → all its skills in the card; repo ID → notice, not in card; explicit item becomes credential-backed → stays, notice; clean item becomes credential-backed → leaves; summary DM once, none on restart, new DM on change, none for 10 restarts (SC-006); a tag map entry changes the tags of one entry and updates the same card (SC-009).
- One stub-claude test checks the command flags (`--plugin-dir`, `--mcp-config`, `--allowedTools`). A manual run with the real `claude` is in [quickstart.md](quickstart.md).

### D14. Dependencies
| Dependency | Why |
|---|---|
| `pyyaml` (already in 001) | Parse the YAML frontmatter of `SKILL.md` and command files with `yaml.safe_load`. |
| stdlib `json`, `hashlib`, `re`, `pathlib`, `os` | JSON files, sha256, text rules, symlinks. |

No new dependency.

### D15. Owner summary DM (Q5, FR-019, FR-020)
- Decision: at start, after discovery and `exposure_notices`, the pure function `build_summary(caps, exposed, notices)` returns `Summary(text, hash)`. `text` has one count line (`N exposed, N owner-only, N skipped`) and one line per notice (`<kind> <id>: <fixed sentence>`). `hash` = sha256 hex of `text`. The pure function `decide_dm(new_hash, last_hash)` returns `send` or `none`. `send_summary` (I/O, `src/pipe/owner_summary.py`) opens the DM with the config `owner` (`conversations.open`, scope `im:write`), posts the text with `post_message`, and then writes `summary_hash` to `state.json`. If the post fails, it logs the error and does not write the hash, so the next start tries again. An empty `owner` gives no DM and a log line.
- The text has names, IDs, and counts only. It passes `scrub` and `escape_mentions` (001). No path, URL, or token.
- No `hidden` count exists: there is no `hidden:` key (Q3). The owner-only items are the hidden items.
- Rationale: the DM tells the owner about a change at once. The hash stops a restart loop from sending the same DM again.

### D16. Where the load-set builder lives
- Decision: `load_set(caps, exposed, capability_ids)` is a pure function of the `claude` runtime adapter. The files are `src/pipe/runtime_claude_loadset.py` (pure), `src/pipe/runtime_claude_load.py` (I/O), and `src/pipe/runtime_claude.py` (`build_cmd`). The input `capability_ids` is a list of IDs from the card. The function keeps an item only when the ID matches a discovered item and its state is `exposed` now (second check at run time). An ID with no match, or an ID that is not exposed, is not loaded and gives a `skipped` notice. `exposed` stays an input, so the builder cannot load an `owner-only` item.
- Rationale: constitution principle XI. The core sends capability IDs only. The words plugin, skill, `--plugin-dir`, and `mcp__` stay in the adapter.
- Alternative: a `capabilities` package shared by the core. Rejected: the core would import runtime-specific code.

### D17. Core and adapter split of the capability rules (principle XI)
- Decision (owner, 2026-11-26): the Claude Code rules move to the `claude` runtime adapter. `src/pipe/runtime_claude_capability.py` holds `ClaudeCapability`, `parse_frontmatter`, `find_signals`, and `assign_ids`. `src/pipe/runtime_claude_exposure.py` holds `SAFE_TOOLS`, `classify`, `to_core`, and `render_list`. The core keeps `Capability` and `Notice` (`core/capability.py`), `state_of`, `exposed_by`, and `exposure_notices` (`core/exposure.py`), `card.py`, and `summary.py`. The adapter classifies each item and gives the core one `Capability` with the result (`role`, `open`, `group`, `tags`, `declared_tags`). The core consumes it. The core never imports the adapter.
- `src/pipe/runtime_claude_discovery.py` reads Claude Code files and is outside `core/`. It is part of the `claude` adapter. It builds `ClaudeCapability` values. It is in the forbidden-import list of the import-boundary test (003 T071).
- Rationale: the safe tool set, `mcp__`, and the credential signs are Claude Code terms. A new runtime would bring its own classification and the same core.
- Consequence: the 003 import-boundary test covers `capability.py`, `exposure.py`, `card.py`, and `summary.py` as core modules (T071 of 003).

### D18. Tag sources (FR-023, owner decision 2026-11-26)
- Decision: the tags of a capability come from two sources: the frontmatter `tags` (lower case, at most 8) and the owner config map `tags: {<capability_id>: [<tag>, ...]}`. The map wins for a capability that has an entry: its list replaces the frontmatter tags. The adapter tags (type, plugin name) stay. `resolve_tags(cap, tag_map)` in `core/card.py` does this. An ID in the map that matches no discovered capability gives the notice `unknown_tag_id`.
- Rationale: plugins of other people (for example wiz-review) have no tags. The owner must be able to mark them, for example as `review`. The core finds a review capability only by the tag.

### D19. Declared capabilities (owner decision 2026-11-26)
- Decision: the owner can declare capabilities in the config key `capabilities`. The shape is in data-model.md "Declared capability". `exec` runs a local command. `http` posts JSON to a URL. A declared capability is one more discovery source. The pure function `declared_caps(entries)` (`src/pipe/declared.py`) builds the core `Capability` values. The ID is `<runtime>:<id>`. The role is `item`, `open` is false, and `classified` is false. So the state is `owner-only` until the ID is in `exposed`, and the clean rule never applies (FR-027). The notice `credential_exposed` does not apply, because the owner exposed it on purpose.
- Config checks (FR-028) run in `validate_config`. They fail the load with the entry `id` in the message and never print a token, a URL, or a command line. The reason for each check: a shell string would run a shell (no shell is used: an argv list); a relative `command[0]` would depend on `PATH`; a token in the file breaks constitution V and the Technology constraint (tokens live in the Keychain, by name); a URL with user info would hold a secret; `access: write` has no worktree or MR path for these adapters.
- The runtime kind, command, URL, token, `env_allow`, and `timeout_s` stay in the config. Only the `exec` and `http` adapters (spec 003) read them. They never enter the card, a notice, the summary, or a log line.
- Tags: the entry `tags` are the `declared_tags`. The tag map `tags` replaces them (FR-023). The adapter tag is the runtime kind.
- The listing, the summary, and the card treat a declared item like any other `item`. `render_list` takes core `Capability` values, so the type column comes from the ID prefix.
- Rationale: the owner can add any tool, script, or service without a Claude skill. The core stays unchanged: it sees a `Capability`. Rejected: a separate registry file (a second place to keep in sync); declared capabilities that are exposed by default (breaks principle III).

### D20. Capability schemas and the validator (FR-029, FR-030)
- Decision: a capability may carry `input_schema` and `output_schema`. They use a JSON Schema subset in the A2A style. Supported keywords: `type` (`object`, `array`, `string`, `number`, `integer`, `boolean`, `null`), `properties`, `required`, `items`, `enum`, `minLength`, `maxLength`, `minimum`, `maximum`, `additionalProperties` (a boolean only), and the annotations `title` and `description`. Any other keyword (for example `$ref`, `oneOf`, `pattern`) is an error at config load. The limits are 2000 characters as canonical JSON and 5 levels of depth.
- Validator choice: a small stdlib validator, `core/schema.py`, with `check_schema(schema)` (is the schema inside the subset) and `validate_schema(instance, schema)` (a list of error sentences). The budget is about 50 lines. It adds no dependency (principle IX). The `jsonschema` package was rejected: it is a new dependency for a feature that needs 10 keywords, it supports far more than the card may carry, and a silent pass on an unknown keyword is the risk of a partial validator, which `check_schema` removes by refusing unknown keywords. If the validator grows past about 80 lines, the plan changes to the `jsonschema` package. That change needs a reason in the plan (principle IX).
- Where the schemas are used: 002 puts them in the card (`build_card`, `validate_card`). Spec 003 validates the step `payload` before a run and the result `data` after it. Spec 001 contracts say how a runtime adapter passes `output_schema` to its runtime.
- The card scan (FR-029): every string value in a schema is checked for a URL, a token-like string, and a path. A violation is a config error (the owner fixes the file), and `validate_card` is the second wall.
- Rationale: a schema lets a planner and a caller check data before they spend a run. Rejected: schemas for Claude skills in this version (no source; the tag map pattern can add a source later).

### D21. Decisions of 2026-11-26, second batch (constitution 1.3.0)
- **E1.** An exposed `exec` capability MUST have an `input_schema`. Reason: the payload comes from another person and goes to a local command. The schema is the only shape check before the run (spec 003 FR-032). The check sits in `validate_config`, because `capabilities` and `exposed` are both config keys. An `http` capability needs no schema: its remote side checks the input. Rejected: a schema for every declared capability (too strict for a private read tool).
- **E2.** Declared capabilities are `read` only. `http` uses `https`, except for `localhost` and `127.0.0.1`. These rules were already in FR-028. The owner confirmed them.
- **E3.** The card and task wire fields keep their names (`bot_id`, `bot_user_id`, `by`, `owner`). Rejected: a rename to neutral names on the wire. It breaks every published card and adds no value, because the core reads them as opaque ids.

## Cannot verify on this machine

- A1: the Slack limit for the size of `metadata`, and the length of a card with many skills. Mitigation: each description is cut to 200 characters, and each schema is at most 2000 characters (D20). If a card is too large, `chat.postMessage` fails; `sync_card` logs the error and the adapter keeps running. There is no size guard in 002. The quickstart has a manual check with 30 skills.
- A2: `pins.add` and `pins.list` behavior in `#pipe-agents` with the real bot (scopes `pins:write`, `pins:read`). No Slack access here.
- A3: a skill that uses `${CLAUDE_PLUGIN_ROOT}` or sibling files may fail in the generated plugin (D6 ceiling).
- A4: the permission to call an exposed MCP tool needs `--allowedTools "mcp__<server>"` under `dontAsk` (assumed; P9 checked only that the tool exists).
- A5: that slash commands in `commands/` of the generated plugin run through the Skill tool in every case. P8 showed them listed as `pipe-exposed:<name>`. A real call is not checked.
- A6: `claude.ai` connector MCP servers cannot be passed with `--mcp-config` (not tested).
- A7: `conversations.open` with `im:write` and a DM post by the bot to the owner. No Slack access here. Checked by the manual run (quickstart).
