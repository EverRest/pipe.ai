# Feature Specification: Discovery and Exposure

**Feature Branch**: `002-discovery-exposure`

**Created**: 2026-11-25

**Status**: Draft

**Input**: User description: "When the adapter starts, it finds what the agent can do: plugins, skills, MCP servers, slash commands, and repos. It shows the owner the list. Capabilities that use the owner's credentials are hidden by default. The owner chooses what to expose. The agent publishes its exposed capabilities as a pinned card in `#pipe-agents`. When the capabilities change, the card is updated."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover capabilities and show them to the owner (Priority: P1)

When the adapter starts, it finds the capabilities of the agent: plugins, skills, MCP servers, slash commands, and repos. It shows the list to the owner. Each item shows if it is exposed or `owner-only`.

**Why this priority**: The owner must see what the agent can do before the owner can decide what to share.

**Independent Test**: Start the adapter on a laptop with known skills and one MCP server. Check that the list shows all of them.

**Acceptance Scenarios**:

1. **Given** the laptop has plugins, skills, MCP servers, slash commands, and repos, **When** the adapter starts, **Then** the owner sees all of them in one list.
2. **Given** a new skill was added after the last start, **When** the adapter starts, **Then** the list includes the new skill.

---

### User Story 2 - Hide credential-backed capabilities by default (Priority: P1)

A capability that uses the owner's credentials is `owner-only`. This includes any MCP server and any skill that calls an external system with the credentials of the user. Other people cannot use it until the owner exposes it.

**Why this priority**: This protects the owner from misuse of the owner's credentials by other agents.

**Independent Test**: Add an MCP server. Check that it is `owner-only` and not in the card. Expose it. Check that it appears.

**Acceptance Scenarios**:

1. **Given** the agent has an MCP server, **When** the owner has not exposed it, **Then** it is `owner-only` and not in the published card.
2. **Given** a capability is `owner-only`, **When** the owner exposes it, **Then** other agents can see it in the card.
3. **Given** a capability was exposed, **When** the owner removes it from the exposed list, **Then** it returns to `owner-only` and leaves the card at the next update.
4. **Given** the owner lists a plugin ID in the exposed list, **When** the adapter starts, **Then** all skills of that plugin are exposed. A credential-backed skill of that plugin is also exposed, and the owner gets a notice.
5. **Given** a skill has only safe `allowed-tools` and no credential signs, **When** the adapter starts, **Then** it is exposed with no owner action.
6. **Given** the owner exposed an item by name or by plugin ID, **When** the item becomes credential-backed, **Then** it stays exposed and the owner gets a notice. **Given** the item was exposed only because it is clean, **Then** it leaves the card.
7. **Given** the adapter starts, **When** the summary of the list and the notices differs from the last summary sent, **Then** the owner gets one Slack DM with the counts and all notices.
8. **Given** the adapter restarts, **When** the summary did not change, **Then** the owner gets no DM.

---

### User Story 3 - Publish and update the agent card (Priority: P2)

The agent publishes its exposed capabilities as one pinned card in `#pipe-agents`. When the exposed capabilities change, the adapter updates the same card.

**Why this priority**: Other agents and planners need the card to know what each agent can do.

**Independent Test**: Start the adapter. Check that one pinned card exists. Add a skill. Restart. Check that the same card shows the new skill.

**Acceptance Scenarios**:

1. **Given** the agent has no card, **When** the adapter starts, **Then** one card is posted and pinned in `#pipe-agents`.
2. **Given** a new exposed skill appears, **When** the adapter starts, **Then** the card is updated within that start. No second card appears.
3. **Given** the exposed capabilities did not change, **When** the adapter starts, **Then** the card is not changed.
4. **Given** the card is published, **When** a person reads it, **Then** it has no URLs, tokens, or local paths.
5. **Given** the card is published, **When** another adapter reads it, **Then** it finds the Slack user ID of the bot (`bot_user_id`) and a stable `id` for each capability.
6. **Given** an exposed skill of another plugin has no `tags` in its frontmatter, **When** the owner adds `tags: {<capability_id>: [review]}` to the config and the adapter starts, **Then** the card entry of that skill has the tag `review`, and the same card is updated.
7. **Given** a skill has frontmatter `tags` and the config map has an entry for its ID, **When** the adapter builds the card, **Then** the list of the config map replaces the frontmatter tags of that skill.

---

### User Story 4 - Declare my own capability in config (Priority: P2)

The owner can declare a capability in the config file. It is a local command (`exec`) or an HTTP endpoint (`http`). It is another discovery source, next to Claude skills and MCP servers. It is `owner-only` until the owner exposes it. Then it goes in the card like any other capability. A capability can have an optional input schema and an optional output schema.

**Why this priority**: The owner can add any tool to the team without a Claude skill. This keeps the core flexible.

**Independent Test**: Declare one `exec` capability. Check that it is `owner-only` and not in the card. Expose it. Check that the card has it, with no command and no URL.

**Acceptance Scenarios**:

1. **Given** the config has a declared capability, **When** the adapter starts, **Then** `pipe capabilities` lists it as `owner-only` with the type `exec` or `http`.
2. **Given** a declared capability is `owner-only`, **When** the owner adds its ID to `exposed`, **Then** the card has an entry with the same `id`, name, description, tags, and access.
3. **Given** a declared capability has `input_schema` or `output_schema`, **When** the owner exposes it, **Then** the card entry holds the schemas.
4. **Given** a declared capability is exposed, **When** another person reads the card, **Then** the card has no command, no URL, no token, no environment name, and no runtime kind.
5. **Given** the config entry has a plain token, a shell string as command, a relative command path, or a schema outside the supported subset, **When** the adapter loads the config, **Then** the load fails with a clear error.
6. **Given** a declared capability is exposed, **When** the owner removes its ID from `exposed`, **Then** it leaves the card at the next update.

### Edge Cases

- A declared capability has the same `id` as another declared capability of the same runtime. The config load fails.
- A declared capability has `access: write`. The config load fails (confirmed decision, see Assumptions).
- An `exec` capability is in `exposed` and has no `input_schema`. The config load fails (FR-031).
- A schema has a URL or a path in a string value. The config load fails, because the card must hold no URL, no token, and no path.
- A skill has the same name as a skill of another plugin.
- A capability changes from not credential-backed to credential-backed after an update.
- The owner exposes a capability that does not exist any more.
- The card message was deleted or unpinned by a person.
- A repo path or an MCP URL appears in the description of a capability.
- No capability is exposed. The card still exists with an empty list.
- The owner lists a repo ID. The repo stays `owner-only`, and the owner gets a notice.
- The adapter restarts in a loop. The owner gets no repeated DM.
- The config map `tags` has an ID that matches no discovered capability. The adapter ignores it, and the owner gets a notice.
- The config map `tags` has an empty list for an ID. The card entry then has only the tags that the adapter adds (the type and the plugin name).
- The owner has no Slack user ID in the config, or the DM fails. The adapter logs it and keeps running.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST find plugins, skills, MCP servers, slash commands, and repos of the agent when the adapter starts.
- **FR-002**: The system MUST show the discovered list to the owner, with the exposure state of each item.
- **FR-003**: The system MUST mark any MCP server as `owner-only` by default.
- **FR-004**: The system MUST mark any skill that calls an external system with user credentials as `owner-only` by default.
- **FR-005**: The system MUST NOT share an `owner-only` capability until the owner exposes it.
- **FR-006**: The owner MUST be the only person who can change what is exposed.
- **FR-007**: The system MUST publish exposed capabilities only, as one card per agent, pinned in `#pipe-agents`.
- **FR-008**: The card MUST show the agent name, description, owner, bot ID, bot user ID, kind, mode, and the list of exposed skills with ID, name, description, and tags, and with optional access and schemas (FR-029).
- **FR-009**: The card MUST NOT contain MCP URLs, tokens, local paths, or config content.
- **FR-010**: The system MUST compute a hash of the exposed skills list. It MUST put the hash in the card.
- **FR-011**: The system MUST update the existing card, and MUST NOT post a new card, when the hash changes.
- **FR-012**: The system MUST NOT change the card when the hash did not change.
- **FR-013**: The system MUST update the card in the same adapter start in which a capability change is found.
- **FR-014**: The system MUST ignore an exposed name that has no matching discovered capability, and MUST tell the owner.
- **FR-015**: The system MUST expose a clean skill with no owner action. A skill is clean when all its `allowed-tools` are in the safe set and it has no credential signs. There is no key to hide a clean skill.
- **FR-016**: An exposed-list entry with a plugin ID MUST expose all skills of that plugin. The system MUST still check each skill for credential signs. A credential-backed skill of an explicitly exposed plugin MUST be exposed, and the owner MUST get a notice.
- **FR-017**: A repo MUST be listed to the owner only. It MUST always be `owner-only` and MUST NOT enter the card. Repo work belongs to spec 004.
- **FR-018**: An item that the owner exposed by name or by plugin ID MUST stay exposed when it becomes credential-backed, and the owner MUST get a notice. An item exposed only by the clean rule MUST leave the card when it becomes credential-backed.
- **FR-019**: At adapter start, the system MUST send the owner one Slack DM with a short summary: the counts of exposed, `owner-only`, and skipped items, and all notices. The owner also sees the list and the notices in `pipe capabilities` and in the adapter log (FR-002, FR-014).
- **FR-020**: The system MUST send the summary DM only when the summary differs from the last summary sent. It MUST store a hash of the last summary in the adapter state directory. A restart loop MUST NOT send repeated DMs.
- **FR-021**: The card MUST hold `bot_user_id`, the Slack user ID of the bot. The adapter MUST get it from `Transport.whoami` (Slack: `auth.test`) when it publishes the card. The adapter MUST NOT need the `users:read` scope for it. Other adapters use it to mention this agent as `<@bot_user_id>`.
- **FR-022**: Each card entry MUST have a stable `id` (the capability ID). An item MUST keep the same `id` across restarts, across discovery order, and across changes of its description. The core of specs 003 and 004 uses this `id` as `capability_id` and uses no other discovery data.
- **FR-023**: The tags of a card entry MUST come from two sources: the `tags` list of the item frontmatter (lower case, at most 8) and the optional owner config map `tags: {<capability_id>: [<tag>, ...]}`. The config map MUST win for a capability that has an entry: its list replaces the frontmatter tags of that capability. The tags that the runtime adapter adds (the type and the plugin name) stay. A tag `review` marks a review capability. The core finds a review capability only by this tag. Reason: plugins of other people (for example wiz-review) have no tags, and the owner must be able to mark them.
- **FR-024**: The load-set builder MUST belong to the `claude` runtime adapter. It MUST take capability IDs as input. It MUST add only items that are exposed at run time. The core MUST NOT import it.
- **FR-025**: The rules that read Claude Code data MUST belong to the `claude` runtime adapter: the frontmatter reader, the safe tool set, the credential signs (including `mcp__`), the capability types, and the classification (`open` or not). The core MUST keep only agnostic types and rules: the capability ID, the state `exposed` or `owner-only`, `exposed_by`, the notices, the card, and the summary. The adapter classifies each item. The core consumes the result. No 002 core module names a plugin, a skill, an MCP server, or a runtime tool.
- **FR-026**: The owner MAY declare capabilities in the config key `capabilities`: `[{id, name, description, tags, access, runtime: exec|http, ...runtime fields, input_schema?, output_schema?}]`. The adapter MUST treat them as one more discovery source. The capability ID is `<runtime>:<id>`, for example `exec:lint-repo`. A declared capability MUST appear in `pipe capabilities`, in the summary, and (when exposed) in the card.
- **FR-027**: A declared capability MUST be `owner-only` by default. Only an entry in `exposed` exposes it. The clean rule MUST NOT apply to it. No notice of the kind `credential_exposed` follows from an explicit exposure of a declared capability.
- **FR-028**: The config load MUST reject: a missing or unknown `runtime`; an unknown key; a duplicate ID; an `exec` `command` that is not an argv list of strings or whose first item is not an absolute path; an `http` `url` that is not `https://` (the hosts `localhost` and `127.0.0.1` may use `http://`) or that holds a user name, a password, or a token; a `token` value that is not `keychain:<service>`; `access` other than `read` (a declared `exec` or `http` capability with `access: write` is a config error; confirmed by the owner on 2026-11-26); an `env_allow` item that is not a plain variable name. A token MUST NOT be in the config file. The `https://` rule and the `localhost` and `127.0.0.1` exception are confirmed on 2026-11-26 (constitution 1.3.0).
- **FR-029**: A card entry MAY hold `access`, `input_schema`, and `output_schema`. It MUST NOT hold the runtime kind, a command, a URL, a token, an environment name, or a timeout. `validate_card` MUST reject a card that holds a URL, a token-like string, or a path in any schema string.
- **FR-030**: The adapter MUST accept only a supported subset of JSON Schema (research.md D20). It MUST reject at config load any schema that uses another keyword, or that is larger than 2000 characters (as canonical JSON), or deeper than 5 levels. The subset check is a pure function without a new dependency.

- **FR-031**: An `exec` capability that is in `exposed` MUST have an `input_schema`. The config load MUST fail when it has none. The error names the entry `id`: `capability exec:<id> is exposed and has no input_schema`. An `exec` capability that is not exposed MAY have no schema. An `http` capability needs no schema (constitution 1.3.0). Reason: an exposed `exec` capability runs a local command with a payload from another person. The schema limits what the payload can hold.
- **FR-032**: The wire field names of the card stay as they are: `bot_id`, `bot_user_id`, `owner`, and the task field `by` (owner decision of 2026-11-26). The core reads them as the opaque `agent_id`, `handle`, and `card_owner_id`. No rename to neutral names happens on the wire.

### Key Entities

- **Capability**: One thing that the agent can do. The core sees an ID, a name, a description, tags, a role (item, group, or listed only), the class that the adapter gave (`open` or not), and an exposure state (`owner-only` or exposed). The `claude` adapter also knows the type (plugin, skill, MCP server, slash command, repo).
- **Exposure list**: The list of capability IDs that the owner chose to share. An ID can name a skill, a command, an MCP server, or a plugin. The owner controls it.
- **Declared capability**: A capability that the owner writes in the config key `capabilities`. It has a runtime kind (`exec` or `http`), and optional schemas. The core sees only the generic `Capability` fields.
- **Capability schema**: An optional `input_schema` or `output_schema` (JSON Schema subset, A2A style). It sits in the config entry and in the card entry.
- **Tag map**: The optional owner config map `tags` from a capability ID to a list of tags. It replaces the frontmatter tags of that capability.
- **Agent card**: The public description of the agent. It has the exposed capabilities (with stable IDs and tags), the bot user ID, and the hash.
- **Card hash**: A fingerprint of the exposed skills list. It shows if the card is out of date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a new skill is added, the card shows it after one adapter start, in 100% of tests.
- **SC-002**: In 100% of tests, a credential-backed capability is absent from the card until the owner exposes it.
- **SC-003**: A scan of 100% of published cards finds no URL, token, or local path.
- **SC-004**: Each agent has exactly one card in `#pipe-agents`, also after 10 restarts.
- **SC-005**: The owner can review the full list and expose one capability in under 5 minutes.
- **SC-006**: After 10 restarts with no change, the owner gets at most 1 summary DM, in 100% of tests. After a change of the list or the notices, the owner gets 1 new DM.
- **SC-007**: In 100% of tests, the card has `bot_user_id` equal to the value of `auth.test`, and the adapter makes no `users.info` and no `bots.info` call.
- **SC-008**: In 100% of tests, the `id` of each card entry is the same after a restart and after a change of the discovery order.
- **SC-009**: In 100% of tests, an entry of the tag map replaces the frontmatter tags of that capability in the card, and a capability with no entry keeps its frontmatter tags.
- **SC-010**: In 100% of builds, no 002 core module (`capability`, `exposure`, `card`, `summary`, `schema`) imports a `claude` adapter module or names a runtime tool, a plugin, a skill, or an MCP server (the import-boundary test of spec 003).
- **SC-011**: In 100% of tests, a declared capability is absent from the card until its ID is in `exposed`.
- **SC-012**: In 100% of tests, a scan of the card of an agent with an exposed `exec` capability and an exposed `http` capability finds no command, no URL, no token, no environment name, and no runtime kind.
- **SC-013**: In 100% of tests, a config entry that breaks a rule of FR-028 or FR-030 fails the config load with an error that names the entry `id`.
- **SC-014**: In 100% of tests, a config that exposes an `exec` capability with no `input_schema` fails the load. The same config with an `input_schema`, with the capability not exposed, or with an `http` capability and no schema, loads.
- **SC-015**: In 100% of tests, a card holds the keys `bot_id`, `bot_user_id`, and `owner`, and `validate_card` rejects a card that holds the keys `agent_id`, `handle`, or `owner_id` in their place.

## Assumptions

- Spec 001 (adapter core and status) exists. The adapter and the channels are in place.
- The channel `#pipe-agents` exists.
- Discovery reads the local Claude Code plugin, skill, MCP, and command configuration.
- The owner edits the exposure list and the tag map in the local config file.
- The classification rule is simple and conservative: when unsure, treat the capability as `owner-only`.
- This feature does not enforce exposure at run time for foreign tasks. Specs 003 and 004 use the exposure data.
- This feature does not load exposed capabilities into any run. It only provides the load-set builder. Specs 003 and 004 pass capability IDs and an access level. The `claude` runtime adapter builds the load set from the IDs.
- The bot has the Slack scopes `chat:write` (from spec 001) and `im:write` (new) to send the summary DM. (These are scopes of the Slack transport adapter.)
- A declared capability supports `access: read` only in this version. A declared `write` capability needs a worktree and an MR path that the `exec` and `http` adapters do not have. The owner confirmed this on 2026-11-26 (constitution 1.3.0): declared capabilities are `read` only.
- The `exec` and `http` runtime adapters (spec 003) run the declared capabilities. 002 only discovers, classifies, exposes, and publishes them.
- Claude skills and MCP servers have no schema source in this version. Only declared capabilities carry schemas.

## Notes for /speckit-plan

- Read the Claude Code plugin, skill, and MCP configuration.
- Card format is the A2A AgentCard shape (design brief §5.3). Event type `pipe.card.v1`.
- Hash of the skills list (sha256). Use `chat.update` on hash change.
- Classification rule for `owner-only`: any MCP server, and any skill that calls an external system with user credentials.
- A plugin ID in `exposed` exposes all skills of the plugin. A repo is listed only.
- Summary DM: pure function for the summary and its hash. Hash in `~/.pipe/state.json`. Scope `im:write`.
- Exposure is a pure function with unit tests (constitution principle VII). The classification rule (safe tool set, credential signs) is part of the `claude` adapter. The core `state_of` consumes its result.
- Config key: `exposed` in `~/.pipe/config.yaml` (design brief §5.4). It holds capability IDs.
- The card has `bot_user_id` (from `auth.test`; no `users:read`). `skills[].id` is the stable `capability_id`. The tags come from the frontmatter and from the config map `tags`. The map wins. A `review` tag marks a review capability.
- The load-set builder is part of the `claude` runtime adapter and takes capability IDs (constitution principle XI).
- Declared capabilities: config key `capabilities`, ID `<runtime>:<id>`, `owner-only` by default, `declared.py` builds the core `Capability`. Schema subset validator: `core/schema.py`, no new dependency (research.md D19, D20).
