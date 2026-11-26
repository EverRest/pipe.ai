---

description: "Task list for Discovery and Exposure"
---

# Tasks: Discovery and Exposure

**Input**: Design documents from `/specs/002-discovery-exposure/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md. Spec 001 is implemented (its modules, ports, and fakes exist).

**Mentions**: `escape_mentions` and `mention` in this file mean the functions of the injected `Formatter` of the `Transport` (spec 001 contracts/transport.md). The core has no mention syntax.

**Tests**: Tests are required. Constitution principle VII (NON-NEGOTIABLE): every pure-function business rule has a test task BEFORE its implementation task. The test must fail first. Tests use fakes and `tmp_path` trees: no real Slack and no real Claude.

**Organization**: Tasks are grouped by user story. Paths follow the Source Code layout in [plan.md](plan.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US3, from [spec.md](spec.md)
- Test tasks start with "Write failing test".

## Path Conventions

Single project: `src/pipe/`, `tests/unit/`, `tests/integration/`, `tests/fakes.py` at the repository root (same as 001).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the files. Check the 001 baseline.

- [ ] T001 Create the empty new files from the plan: `src/pipe/core/capability.py`, `src/pipe/core/exposure.py`, `src/pipe/core/card.py`, `src/pipe/core/summary.py`, `src/pipe/core/schema.py`, `src/pipe/capset.py` (the `collect` helper that the CLI and the adapter use), `src/pipe/declared.py`, `src/pipe/runtime_claude_capability.py`, `src/pipe/runtime_claude_exposure.py`, `src/pipe/runtime_claude_loadset.py`, `src/pipe/runtime_claude_discovery.py`, `src/pipe/card_sync.py`, `src/pipe/owner_summary.py`, `src/pipe/runtime_claude_load.py`, `tests/manual/` (directory only)
- [ ] T002 Run `pytest tests/unit tests/integration` for spec 001. All tests must pass before 002 work starts. Do not add a dependency (research.md D14)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Capability type, config keys, the exposure rule, ports, and fakes that every story needs

**CRITICAL**: No user story work starts before this phase is complete.

- [ ] T003 [P] Write failing test for the Claude Code capability helpers in `tests/unit/test_runtime_claude_capability.py` (data-model.md ClaudeCapability, research.md D1, D3, D17). This is a test of the `claude` adapter, not of the core:
  - `parse_frontmatter` returns the frontmatter dict and the body for `---` blocks. A `tags` list in the frontmatter becomes `ClaudeCapability.declared_tags` after `sanitize_tags` (FR-023). It handles folded `description: >` text. It returns an empty dict and the full text when there is no frontmatter. It raises `ValueError` for invalid YAML.
  - `find_signals(text)` finds each credential signal of research.md D3 (`mcp__`, a URL, `token`, `api key`, `secret`, `password`, `credential`, `oauth`, `login`, `.env`, `_TOKEN` names, `curl`, `ssh`, `glab`, `kubectl`, `git push`). It is case-insensitive. It returns signal names, not text. Plain text returns `()`.
  - `assign_ids` gives `skill:<name>` to a personal skill and `skill:<plugin>:<name>` to a plugin skill. The same for `command`, `mcp`, `plugin`, `repo`.
  - Two items with the same ID get the suffix `#<6 hex of sha256 of source_key>`. The suffix is stable when the input order changes. Items without a collision keep a plain ID.
  - The ID of an item is the same after a second `assign_ids` run, after a change of the input order, and after a change of the description (FR-022, SC-008). The ID holds no path.
- [ ] T004 Implement `ClaudeCapability`, `parse_frontmatter`, `find_signals`, and `assign_ids` in `src/pipe/runtime_claude_capability.py` (T003; depends on T049 for `sanitize_tags`; uses `yaml.safe_load`)
- [ ] T005 [P] Write failing test for the new config keys in `tests/unit/test_config.py` (data-model.md Exposure list and Tag map, research.md D11, D18):
  - `exposed` is a list of non-empty strings. Default `[]`. A wrong type is an error.
  - `tags` is a map from a non-empty string (a capability ID) to a list of tags. Default `{}`. A wrong type is an error. A tag that is not lower case `[a-z0-9-]`, is longer than 32 characters, or a list with more than 8 tags is an error. An empty list is valid (FR-023).
  - `description` is optional. Default `Claude Code agent <agent_name>`. Maximum 200 characters.
  - `agents_channel` default is `pipe-agents`.
  - 001 behavior is unchanged: `allowlist` is still accepted and ignored. Update the 001 case "`allowlist` and `exposed` are accepted and ignored" in this file: `exposed` is now validated and used.
- [ ] T006 Implement the validation of `exposed`, `tags`, `description`, and `agents_channel` in `src/pipe/config.py` (T005)
- [ ] T007 [P] Write failing test for `state_of` and `exposed_by` in `tests/unit/test_exposure.py` (FR-005, FR-015 to FR-018, FR-025, research.md D4). The test uses hand-made core `Capability` values with opaque IDs and no adapter module:
  - A `listed_only` item is `owner-only`, also when its ID is in `exposed` (FR-017). A `group` item is `exposed` only when its ID is in `exposed`, and it is never a card entry.
  - An `item` with `open` true is `exposed` with an empty `exposed` list and `exposed_by` = `clean` (FR-015). No `hidden` key exists in the config schema.
  - An `item` with `open` false is `owner-only`.
  - An ID in `exposed` makes a not-open `item` `exposed`, with `exposed_by` = `owner`.
  - A `group` ID in `exposed` makes every item with that `group` `exposed`, with `exposed_by` = `owner` (FR-016). An item of another group is not changed. A not-open item of the exposed group is `exposed`.
  - Removing an ID from `exposed` returns the item to `owner-only` (US2 scenario 3).
  - Path A (FR-018): an item that the owner listed by ID, or by `group` ID, stops being `open`. It stays `exposed` and `exposed_by` = `owner`.
  - Path B (FR-018): an item that was exposed only by the clean rule stops being `open`. It becomes `owner-only`.
  - The same input always gives the same result. The function does not change its input.
- [ ] T008 Implement `state_of` and `exposed_by` in `src/pipe/core/exposure.py` (T007; depends on T049)
- [ ] T009 [P] Extend `tests/fakes.py` (depends on 001 fakes):
  - `FakeTransport` gets `update_message(channel, ts, text, metadata)`, `pin(channel, ts)`, `list_pins(channel)`, `history(channel, limit)`, and an optional `metadata` argument on `post_message`. It records every call. It can fail `update_message` with `message_not_found` on demand. It can delete or unpin a message on demand. It has `send_dm(user_id, text)`, can fail on demand, and records every DM post. `whoami` returns an `Identity`.
  - `build_claude_tree(tmp_path)` builds a fake home: `installed_plugins.json`, `settings.json` with `enabledPlugins`, plugin directories with `.claude-plugin/plugin.json`, `skills/*/SKILL.md`, `commands/*.md`, `~/.claude/skills`, `~/.claude/commands`, `~/.claude.json` with `mcpServers` (fake URLs and fake secret headers), and two repos with `.git` under a fake `runtime.claude.repo_roots`. One fake plugin has a clean skill and a credential-backed skill.
- [ ] T010 [P] Check that the `Transport` Protocol of 001 (`src/pipe/ports.py`, 001 contracts/transport.md) has `update_message`, `pin`, `list_pins`, `history`, `send_dm(user_id, text)`, and the optional arguments `thread (default none: a top-level post)` and `metadata` of `post_message`. Add what is missing. `whoami` returns an `Identity` (`agent_id`, `handle`: the card `bot_id` and `bot_user_id`; contracts/card.md)
- [ ] T048 [P] Write failing test for the core `Capability`, `Notice`, and `sanitize_tags` in `tests/unit/test_capability.py` (data-model.md Capability, FR-023, FR-025):
  - `Capability` has the fields `id`, `name`, `description`, `role`, `open`, `group`, `tags`, `declared_tags`, and the fields `runtime` (default `claude`), `access`, `input_schema`, `output_schema` (default `None`), and `classified` (default true). It is frozen. An empty `id` or `name` raises `ValueError`. A `role` outside `item`, `group`, and `listed_only` raises `ValueError`.
  - `sanitize_tags` keeps lower case `[a-z0-9-]` tags of at most 32 characters. It drops others and duplicates. It keeps at most 8 tags, in input order. It returns a tuple.
  - The module imports no `claude` adapter module and holds no term `plugin`, `skill`, `mcp`, or tool name (the 003 test T071 checks the same later).
- [ ] T049 Implement `Capability` (with the fields `runtime`, `access`, `input_schema`, `output_schema`, `classified`), `Notice`, and `sanitize_tags` in `src/pipe/core/capability.py` (T048)
- [ ] T050 [P] Write failing test for `classify` and `to_core` in `tests/unit/test_runtime_claude_exposure.py` (FR-003, FR-004, FR-015, FR-025, research.md D3, D17). This is a test of the `claude` adapter:
  - `classify` of any `mcp`, `plugin`, or `repo` item is `owner-only`.
  - A skill with `allowed_tools` in the safe set and no signal is `open`.
  - A skill with no `allowed_tools` is `owner-only` (unsure).
  - A skill with an unsafe tool (`Bash`, `WebFetch`, `mcp__x`) is `owner-only`.
  - A skill with a safe tool list and one signal in the body is `owner-only`.
  - `to_core` maps `skill` and `command` to role `item` with `open` from `classify`, `group` = `plugin_id`, and `tags` = (type, plugin name if any). It maps `mcp` to role `item` with `open` false. It maps `plugin` to role `group`. It maps `repo` to role `listed_only`. `declared_tags` is copied.
  - The same input always gives the same result. The function does not change its input.
  - `render_list` is tested in T012 (it sits in `core/exposure.py`, T014).
- [ ] T051 Implement `SAFE_TOOLS`, `classify`, and `to_core` in `src/pipe/runtime_claude_exposure.py` (T050; depends on T004, T049)

**Checkpoint**: Foundation ready. User stories can start.

---

## Phase 3: User Story 1 - Discover capabilities and show them to the owner (Priority: P1) MVP

**Goal**: At start, the adapter finds plugins, skills, MCP servers, slash commands, and repos. The owner sees one list with the state of each item.

**Independent Test**: Run `pytest tests/unit/test_runtime_claude_discovery.py tests/integration/test_capabilities_cli.py`. Then do the quickstart scenarios "1".

### Tests for User Story 1 (write first, they MUST fail)

- [ ] T011 [P] [US1] Write failing test for discovery in `tests/unit/test_runtime_claude_discovery.py` with `build_claude_tree` (FR-001, research.md "Discovery sources", D1, D5):
  - It finds enabled plugins only (`enabledPlugins` true). A disabled plugin is ignored.
  - It finds plugin skills, personal skills (also a symlinked directory), plugin commands, and personal commands. It ignores the `synced` directory.
  - It finds MCP servers from `~/.claude.json` and from a plugin (inline object, string path, and `.mcp.json`). It reads names only.
  - It finds repos under `runtime.claude.repo_roots` (directories with `.git`).
  - A new skill directory added after the first run appears in the second run (US1 scenario 2). The IDs of the old items are the same in both runs (FR-022).
  - A `tags` list in the frontmatter of a skill and of a command is in `ClaudeCapability.declared_tags` (FR-023). A skill with the tag `review` keeps it. A skill with no `tags` has an empty `declared_tags`.
  - A skill with bad frontmatter is skipped. The result has a `skipped` notice with the directory base name and no path.
  - Two skills with the same name in two plugins get different IDs (spec edge case).
  - No `ClaudeCapability` field holds a fake URL, header, or secret from the fake `~/.claude.json`.
  - Only the key `enabledPlugins` is read from `settings.json`.
  - `ClaudeCapability.source` is set (internal) and is not part of any text that the tests render.
- [ ] T012 [P] [US1] Write failing test in `tests/integration/test_capabilities_cli.py` (FR-002, contracts/cli.md):
  - `pipe capabilities` prints one line per capability: state, type, `id`, `name`. The order is by type, then `id`. A count line follows.
  - The output has no path, no URL, no description text, and no token (fake values from `build_claude_tree` do not appear).
  - The command makes no Slack call and no Keychain call. It exits 0.
  - At adapter start, the same list goes to the adapter log (use `FakeTransport` and a temporary `PIPE_HOME`).
  - `render_list` for an empty discovery prints `0 capabilities`.

### Implementation for User Story 1

- [ ] T013 [US1] Implement `discover(home, repo_roots) -> (list[ClaudeCapability], list[Notice])` and `read_mcp_entries(home) -> dict[str, dict]` in `src/pipe/runtime_claude_discovery.py` (T011; depends on T004). It builds `ClaudeCapability` values. `discover` reads names only. `read_mcp_entries` is the only reader of full entries and is used at run time only (research.md D7)
- [ ] T014 [US1] Implement the pure `render_list(caps, exposed, notices) -> list[str]` in `src/pipe/core/exposure.py` (T012; depends on T008). `caps` are core `Capability` values (the CLI maps `ClaudeCapability` values with `to_core` and declared entries with `declared_caps` first). The function calls the core `state_of`. The type column is the part of the `id` before the colon. Same file as T008 and T021, so it runs after T008
- [ ] T015 [US1] Add the sub-command `pipe capabilities` in `src/pipe/cli.py` (T012; depends on T006, T013, T014, T051; contracts/cli.md). The command reads `exposed`, `tags`, and `runtime.claude.repo_roots`
- [ ] T016 [US1] At adapter start, run `discover` and write `render_list` lines to the adapter log in `src/pipe/adapter.py` (T012; depends on T013, T014). A discovery error is logged and never stops the adapter

**Checkpoint**: User Story 1 works alone. This is the MVP.

---

## Phase 4: User Story 2 - Hide credential-backed capabilities by default (Priority: P1)

**Goal**: An `owner-only` item is not shared until the owner exposes it. A plugin ID exposes all its skills. The owner sees notices and gets one summary DM when it changes. The load builder gives a `--restricted` child only the exposed items. 002 does not load them into any run.

**Independent Test**: Run `pytest tests/unit/test_exposure.py tests/unit/test_summary.py tests/unit/test_runtime_claude_loadset.py tests/unit/test_runtime_claude_load.py tests/unit/test_runtime_claude.py tests/integration/test_owner_summary.py`. Then do the quickstart scenarios "2" (list part). The card part of the scenarios is proven in Phase 5 (T030).

### Tests for User Story 2 (write first, they MUST fail)

- [ ] T017 [P] [US2] Write failing test for `exposure_notices(caps, exposed, tag_map)` in `tests/unit/test_exposure.py` (FR-014, FR-023, data-model.md Notice). The test uses hand-made core `Capability` values:
  - An ID in `exposed` with no discovered item gives `unknown_id` (the owner exposes an item that does not exist any more).
  - An ID of role `listed_only` gives `not_exposable` (FR-017). An ID of role `group` gives no `not_exposable`.
  - An `item` that is exposed by the owner (by its ID or by its `group` ID) and is not `open` gives `credential_exposed` (FR-016, FR-018 path A). A `group` item gives no `credential_exposed`.
  - An item exposed only by the clean rule that stops being `open` gives no notice and is not exposed (FR-018 path B).
  - An ID in `tag_map` with no discovered item gives `unknown_tag_id`. An ID in `tag_map` of a known item gives no notice. An empty `tag_map` gives none.
  - A skipped item gives `skipped`.
  - A declared item (`classified` false) that is exposed by its ID gives no `credential_exposed` (FR-027).
  - Notice text has the `id` and a fixed sentence. It has no path, URL, token, or value from a file.
  - No notice for an `open` item and for a normal `owner-only` item that is not exposed.
- [ ] T018 [P] [US2] Write failing test for `load_set(caps, exposed, capability_ids)` in `tests/unit/test_runtime_claude_loadset.py` (contracts/runtime-load.md, FR-024, research.md D16). The module is part of the `claude` runtime adapter. `caps` are `ClaudeCapability` values (the function calls `to_core` and the core `state_of`):
  - The input is a list of capability IDs. Only items whose ID is in the list enter the set.
  - An ID with no discovered item, and an ID of an item that is not exposed now, do not enter the set. `skipped` has a notice for each (second check at run time).
  - An empty ID list gives an empty set.
  - Only items with state `exposed` and type `skill`, `command`, or `mcp` enter the set.
  - An `owner-only` item that is not exposed never enters the set (FR-005).
  - An `owner-only` item that the owner listed enters the set.
  - `plugin` and `repo` items never enter the set. The skills of a plugin whose ID is in `exposed` enter one by one.
  - Items are sorted by `id`.
  - A set with no exposed item is empty. `needs_skill_tool` is false.
  - Two exposed items with the same `link_name`: the second one is skipped and `skipped` has a notice.
  - `allowed_rules` has `Skill(pipe-exposed:<link_name>)` per skill and command and `mcp__<server>` per server.
- [ ] T019 [P] [US2] Write failing test for `prepare` in `tests/unit/test_runtime_claude_load.py` (research.md D6, D7):
  - It creates `<run_dir>/exposed-plugin/.claude-plugin/plugin.json` with the name `pipe-exposed`.
  - A skill is a symlink in `skills/<link_name>`. A command is a copy in `commands/<link_name>.md`.
  - `mcp.json` has only the exposed servers. It has the full entry (from fake `read_mcp_entries` data). Its mode is 0600. The run dir mode is 0700.
  - No `plugin_dir` when no skill or command is exposed. No `mcp_file` when no server is exposed.
  - A server with no entry is skipped and logged by name.
  - `cleanup(run_dir)` removes the directory. It also works after a failure.
  - No log line, no returned text, and no exception message has a URL, header, or secret from an entry.
- [ ] T020 [P] [US2] Write failing test in `tests/unit/test_runtime_claude.py` for `build_cmd(..., prepared)` (contracts/runtime-load.md):
  - With `prepared=None` the command is equal to the 001 command (regression).
  - With a `PreparedLoad`: `--plugin-dir <dir>`, `--mcp-config <file>` while `--strict-mcp-config` stays, and `Skill` added to `--tools` only when a skill or command is exposed.
  - `--allowedTools` keeps the 001 rules and adds `Skill(pipe-exposed:<name>)` and `mcp__<server>`.
  - `--restricted` and `--permission-mode dontAsk` are in every command.
  - An empty load set adds no flag.
  - With the stub script `tests/stub_claude/claude`, the recorded argv has the new flags.
  - The mention path passes no capability IDs, so `ClaudeRuntime` calls no `prepare` (check in `tests/integration/test_adapter_mention.py`: the argv has no `--plugin-dir` and no `--mcp-config`, and no `pipe-exposed` run dir is created). The load wiring is in 002 inside `ClaudeRuntime` (`run`, `_load`: `load_set`, `prepare`, `cleanup`). It runs only when the run has capability IDs (`inp.request.capability_ids`). The mention path never sets them until spec 003, so mention runs stay as in stage 001.

- [ ] T041 [P] [US2] Write failing test for `build_summary` and `decide_dm` in `tests/unit/test_summary.py` (FR-019, FR-020, research.md D15). The input `caps` are hand-made core `Capability` values:
  - The text has one count line (exposed, `owner-only`, skipped) and one line per notice. All notices are in it.
  - The same input gives the same `hash`. The order of discovery does not change it. A change of one count or one notice changes it.
  - The text has no path, URL, token, or Slack mention syntax. Fake secrets from `build_claude_tree` do not appear.
  - No `hidden` count exists.
  - `decide_dm(new, None)` gives `send`. Equal hashes give `none`. Different hashes give `send`.
- [ ] T042 [P] [US2] Write failing test in `tests/integration/test_owner_summary.py` with `FakeTransport` and `build_claude_tree` (FR-019, FR-020, SC-006):
  - First start: `send_dm` is called with the config `owner`, one DM is posted, and `summary_hash` is saved.
  - Second start with no change: no DM. Ten starts in a row: one DM in total.
  - A new unknown ID in `exposed`: one new DM that has the notice.
  - The DM post fails: the error is logged, `summary_hash` is not saved, the adapter still handles a mention, and the next start sends the DM.
  - Empty `owner`: no DM and a log line.
  - The DM text passes the scan for `http`, `xox`, `/Users`, `~/`.

### Implementation for User Story 2

- [ ] T021 [US2] Implement `exposure_notices` in `src/pipe/core/exposure.py` (T017; depends on T008, same file; takes the core `Capability` values and the `tag_map`)
- [ ] T022 [P] [US2] Implement `LoadSet` and `load_set(caps, exposed, capability_ids)` in `src/pipe/runtime_claude_loadset.py` (T018; depends on T008 and T051). The module belongs to the `claude` runtime adapter. It imports nothing from the pipeline core except the 002 core types and `state_of`
- [ ] T023 [US2] Implement `prepare`, `PreparedLoad`, and `cleanup` in `src/pipe/runtime_claude_load.py` (T019; depends on T013, T022). Use `os.symlink`, `shutil.copyfile`, `os.chmod`, and `shutil.rmtree`
- [ ] T024 [US2] Add the `prepared` parameter to `build_cmd` in `src/pipe/runtime_claude.py` (T020; depends on T023). The default is `None`. The load wiring is in 002 inside `ClaudeRuntime` (`run`, `_load`: `load_set`, `prepare`, `cleanup`). It runs only when the run has capability IDs (`inp.request.capability_ids`). The mention path never sets them until spec 003, so mention runs stay as in stage 001. Spec 003 sets the IDs
- [ ] T025 [US2] Print the notices in `pipe capabilities` (`src/pipe/cli.py`) and in the adapter log at start (`src/pipe/adapter.py`) (T012, T017; depends on T015, T016, T021). The notices are the `skipped` notices of `discover` and the result of `exposure_notices` on the `to_core` values, with `exposed` and `tags` from the config
- [ ] T043 [US2] Implement `Summary`, `build_summary`, and `decide_dm` in `src/pipe/core/summary.py` (T041; depends on T021; uses 001 `scrub` and `escape_mentions`)

**Checkpoint**: User Stories 1 and 2 work. The owner sees the states and the notices. The load builder is ready for specs 003 and 004.

---

## Phase 5: User Story 3 - Publish and update the agent card (Priority: P2)

**Goal**: One pinned card in `#pipe-agents` shows the exposed capabilities. The card is updated in place when the hash changes. The card has no URL, token, or local path.

**Independent Test**: Run `pytest tests/unit/test_card.py tests/unit/test_card_build.py tests/unit/test_card_publish.py tests/integration/test_card_sync.py`. Then do the quickstart scenarios "3".

### Tests for User Story 3 (write first, they MUST fail)

- [ ] T026 [P] [US3] Write failing test for `sanitize_text` and `skills_hash` in `tests/unit/test_card.py` (FR-009, FR-010, research.md D9):
  - A URL (`https://...`, `http://...`, `wss://...`) becomes `[removed]`.
  - A path (`/Users/x/y`, `~/code/x`, `/home/x/y`, `/private/tmp/x`) becomes `[removed]` (spec edge case: a repo path or an MCP URL in a description).
  - A token-like string becomes `[redacted]` through the 001 `scrub`.
  - Spaces are collapsed. The text is cut to 200 characters. Plain text such as `and/or` stays.
  - `skills_hash` has a fixed test vector (hex sha256 of the canonical JSON).
  - The hash is the same for a different input order. It changes when any `skills` field changes. It does not change for a different card `description` or `owner`.
- [ ] T027 [P] [US3] Write failing test for `build_card` and `validate_card` in `tests/unit/test_card_build.py` (FR-007, FR-008, FR-009, data-model.md Agent card). The input `caps` are hand-made core `Capability` values with opaque IDs (the integration test T030 uses `to_core` of the fake tree). `build_card` takes the `tag_map` as the fourth argument:
  - The card has `name`, `description`, `owner`, `bot_id`, `kind` = `agent`, `mode` = `laptop`, `skills`, `hash`. The field `bot_user_id` is tested in T046 and added in T047.
  - `skills` has exposed items of role `item` only, sorted by `id`. Each entry has `id`, `name`, `description`, `tags` (`resolve_tags`: the adapter tags, then the map list or the declared tags).
  - Each `skills[].id` equals the `Capability.id` and equals the ID that the owner writes in `exposed` (FR-022). The tag `review` of the declared tags reaches the card entry. A `tag_map` entry replaces the declared tags in the entry (FR-023, details in T052).
  - An `owner-only` item is never in `skills` (SC-002). A not-open item is absent until its ID is in `exposed`, and present after (US2 scenarios 1 and 2). It leaves when the ID is removed (US2 scenario 3).
  - A `group` ID in `exposed` puts all items of that group in `skills`, including a not-open one (FR-016). A `group` item and a `listed_only` item are never in `skills` (FR-017).
  - A clean skill is in `skills` with an empty `exposed` list (FR-015). A clean item that stops being `open` leaves `skills`. An item listed by the owner that stops being `open` stays (FR-018).
  - No exposed item gives a card with `skills` = `[]` (spec edge case).
  - Empty `owner` or empty `bot_id` raises `CardError`.
  - A description with a URL or a path is sanitized. `validate_card` returns `[]` for every card that `build_card` returns, for inputs with fake URLs, fake paths, and fake tokens in names and descriptions.
  - `validate_card` returns violations for a hand-made card with a URL, a path, or a token (second wall).
  - The card has no `source` value and no value from a fake MCP entry.
  - The card `text` has no Slack mention syntax (`escape_mentions` from 001 is applied).
- [ ] T028 [P] [US3] Write failing test for `decide_publish` and `pick_own_card` in `tests/unit/test_card_publish.py` (FR-011, FR-012, SC-004):
  - No existing card gives `post`. A different hash gives `update`. An equal hash gives `none`.
  - `pick_own_card` returns the newest message with `bot_id` equal to the own bot and `event_type` = `pipe.card.v1`.
  - It ignores messages of other bots and messages with another event type. It returns `None` when there is no match.
  - A card with a forged `bot_id` inside the payload but another author is ignored (principle V).
- [ ] T029 [P] [US3] Write failing test in `tests/unit/test_state.py` for the new `state.json` keys `bot_id`, `agents_channel_id`, `card` (`{channel, ts, hash}`), and `summary_hash` (str): atomic write, mode 0600, round trip, and writing one key keeps the other keys (research.md D11)
- [ ] T030 [P] [US3] Write failing test in `tests/integration/test_card_sync.py` with `FakeTransport` and `build_claude_tree` (SC-001 to SC-004):
  - Start with no card: one card is posted with `metadata` (`pipe.card.v1`) and pinned (US3 scenario 1).
  - Second start, no change: no `update_message` call and no `post_message` call (US3 scenario 3, FR-012).
  - A new `open` skill: the same `ts` is updated in the same start. No second post (US3 scenario 2, FR-013, SC-001). The update call has `text` and `metadata`.
  - An MCP server is not in the card. After its ID is in `exposed`, it is in the card (SC-002). After removal it leaves at the next start.
  - An unknown ID in `exposed` gives a notice and does not change the card (FR-014).
  - A `tags` map entry for an exposed skill that has no frontmatter tags (a plugin skill like wiz-review) gives the tag `review` in the same card entry. The same `ts` is updated (SC-009). Removing the entry removes the tag at the next start. An entry for an unknown ID gives `unknown_tag_id` and does not change the card.
  - A plugin ID in `exposed` puts all its skills in the card. A repo ID in `exposed` gives a notice and the repo is not in the card (FR-016, FR-017).
  - The card is deleted by a person: the next start posts a new card and pins it. `update_message` fails with `message_not_found`: the same result.
  - The card is unpinned: the next start pins it again and does not edit it.
  - `state.json` has no `card` key and the card exists in history: the adapter finds it and posts no second card.
  - Ten starts in a row give one card (SC-004).
  - All text and metadata of every posted card pass a scan for `http`, `xox`, `/Users`, `~/` (SC-003). Fake URLs and secrets from the fake tree never appear.
  - Empty `owner`: no post, a logged notice, and the adapter still handles a mention.
  - A Slack error in `sync_card` is logged. It never stops the adapter.

### Implementation for User Story 3

- [ ] T031 [US3] Implement `sanitize_text` and `skills_hash` in `src/pipe/core/card.py` (T026; depends on 001 `core/scrub.py`)
- [ ] T032 [US3] Implement `Identity`, `Card`, `CardError`, `build_card`, and `validate_card` in `src/pipe/core/card.py` (T027; depends on T008, T031, T053; same file as T031)
- [ ] T033 [US3] Implement `CardState`, `decide_publish`, and `pick_own_card` in `src/pipe/core/card.py` (T028; same file, after T032)
- [ ] T034 [P] [US3] Add the keys `bot_id`, `agents_channel_id`, `card`, and `summary_hash` to `src/pipe/state.py` (T029)
- [ ] T035 [US3] Implement `update_message`, `pin`, `list_pins`, `history`, `send_dm` (`conversations.open`), the `bot_id` in the `whoami` result, and the optional `thread_ts` (top-level post) and `metadata` in `post_message` in `src/pipe/transport_slack.py` over `slack_sdk` (T030; depends on T010; use cursor pagination as in 001)
- [ ] T036 [US3] Implement `sync_card(slack, state, card, notices)` in `src/pipe/card_sync.py` (T030; depends on T033, T034, T035): post and pin, update only on a hash change, pin repair with `list_pins`, new post after `message_not_found`, recovery with `history` and `pick_own_card`, no raise on a Slack error
- [ ] T037 [US3] At adapter start, in `src/pipe/adapter.py` (T030; depends on T016, T025, T036): save `bot_id` from `auth.test`, find `#pipe-agents` with `find_channel(agents_channel)`, build the card from the discovered list: `discover`, then `to_core` for each item, then `build_card` with the config `exposed` and `tags` (T047 adds `bot_user_id` to it), and call `sync_card` before the catch-up pass. Wrap the step in a try block that logs the error
- [ ] T044 [US2] Implement `send_summary(slack, state, owner, summary)` in `src/pipe/owner_summary.py` (T042; depends on T034, T035, T043): open the DM, post, then write `summary_hash`. No raise on a Slack error
- [ ] T045 [US2] At adapter start, in `src/pipe/adapter.py` (T042; depends on T037, T044): build the summary from the core `Capability` values (`to_core`) and the notices, and call `send_summary` after `sync_card`. Wrap the step in a try block that logs the error. This task does not touch any load set
- [ ] T046 [P] [US3] Write failing test for `bot_user_id` in `tests/unit/test_card_build.py` and `tests/integration/test_card_sync.py` (FR-021, SC-007):
  - `Identity` has `bot_user_id`. `build_card` puts it in the card. An empty `bot_user_id` raises `CardError`.
  - `validate_card` returns a violation for a `bot_user_id` that does not match the neutral form `^[A-Za-z0-9._:-]{2,64}$` (second wall). The Slack form (`U` or `W` plus upper-case letters and digits) is checked in the Slack adapter (001 T053), not in the core.
  - The posted card `metadata` has `bot_user_id` equal to the `user_id` that `FakeTransport.whoami` returns.
  - `FakeTransport` records no `users.info` call and no `bots.info` call during start-up and card sync (SC-007). The documented scope list (quickstart) has no `users:read`.
  - A change of `bot_user_id` alone does not change the `hash` and does not update the card (known limit, research.md D9).
  - The card `text` for people holds no mention syntax with `bot_user_id` (`<@U...>` is escaped).
- [ ] T047 [US3] Implement `bot_user_id` in `Identity`, `Card`, `build_card`, and `validate_card` in `src/pipe/core/card.py` (T046; same file, after T033). Read `bot_user_id` from `whoami` in the start-up code of `src/pipe/adapter.py` and pass it into `Identity` (T046; depends on T037)
- [ ] T052 [P] [US3] Write failing test for `resolve_tags` in `tests/unit/test_card_tags.py` (FR-023, SC-009, research.md D18):
  - A capability with no `tag_map` entry gets `cap.tags` and then `cap.declared_tags` (frontmatter tags).
  - A `tag_map` entry for the ID replaces `declared_tags`. `cap.tags` (type, plugin name) stays and comes first. The result has no duplicates.
  - An entry with an empty list gives `cap.tags` only (the declared tags are removed).
  - A capability with no declared tags (a plugin skill of another person, for example wiz-review) and an entry `[review]` gets the tag `review`.
  - A `tag_map` entry for another ID does not change the result.
  - The result tags are `sanitize_tags` clean and at most 8 declared or map tags are used.
  - The result is the same for any order of the `tag_map` keys. The function does not change its input.
  - A change of the `tag_map` that changes the tags of an exposed item changes the card `hash` (test in `test_card_build.py` T027).
- [ ] T053 [US3] Implement `resolve_tags` in `src/pipe/core/card.py` (T052; depends on T049; same file as T031, so it runs before T032)

**Checkpoint**: All three user stories work.

---

## Phase 5A: User Story 4 - Declare my own capability in config (Priority: P2)

**Goal**: The owner declares an `exec` or `http` capability in the config. It is `owner-only` until the owner exposes it. Then the card has it, with its optional schemas, and nothing else about the runtime. The config rejects unsafe entries.

**Independent Test**: Run `pytest tests/unit/test_schema.py tests/unit/test_config.py tests/unit/test_declared.py tests/unit/test_card_build.py tests/integration/test_declared_capabilities.py`. Then do the quickstart scenarios "4".

### Tests for User Story 4 (write first, they MUST fail)

- [ ] T054 [P] [US4] Write failing test for the schema subset validator in `tests/unit/test_schema.py` (FR-030, research.md D20):
  - `check_schema(schema)` returns `[]` for a schema that uses only the supported keywords: `type`, `properties`, `required`, `items`, `enum`, `minLength`, `maxLength`, `minimum`, `maximum`, `additionalProperties` (boolean), `title`, `description`.
  - It returns an error for `$ref`, `oneOf`, `anyOf`, `pattern`, `format`, a non-boolean `additionalProperties`, a `type` outside the seven names, a schema longer than 2000 characters as canonical JSON, and a schema deeper than 5 levels.
  - `validate_schema(instance, schema)` returns `[]` for a valid instance and error sentences for: a wrong type, a missing `required` key, an extra key when `additionalProperties` is false, a value outside `enum`, a string shorter than `minLength` or longer than `maxLength`, a number outside `minimum` and `maximum`, and a bad item of `items`. A boolean is not an `integer` and not a `number`.
  - An error sentence names the path (for example `payload.repo: expected string`). It holds no value from the instance (no secret in an error).
  - The functions do not change their input. The module imports no package outside the standard library and holds no term `plugin`, `skill`, `mcp`, or tool name.
- [ ] T056 [P] [US4] Write failing test for the `capabilities` config key in `tests/unit/test_config.py` (FR-026, FR-028, SC-013, data-model.md "Declared capability"):
  - The default is `[]`. A wrong type is an error.
  - A valid `exec` entry and a valid `http` entry load.
  - (Confirmed by the owner on 2026-11-26: `access: write` and a plain `http://` URL for another host are config errors.) Errors, each with the entry `id` in the message: a missing `runtime`, `runtime: shell`, an unknown key (`shell`, `env`), a missing required key, a duplicate `<runtime>:<id>`, a bad `id` form, `access: write`, a `command` that is a string, a `command` item that is not a string, an empty `command`, a relative `command[0]`, an `env_allow` item such as `A=B`, an `http` `url` with `http://` and a host other than `localhost` or `127.0.0.1`, a `url` with a user name or a password, a `token` that is not `keychain:<service>` (for example `ghp_abc` or `xoxb-1`), an `exec` entry with `url`, an `http` entry with `command`, a `timeout_s` outside 1 to 3600, a tag list with a bad tag, and a schema that fails `check_schema` or that has a string value with a URL, a path, or a token-like string.
  - No error text holds a `command` item, a `url`, or a `token` value.
- [ ] T064 [US4] Write failing test for the `input_schema` rule of exposed `exec` capabilities in `tests/unit/test_config.py` (same file as T056, so it is not parallel; FR-031, SC-014, decision E1):
  - A config with an `exec` entry `lint-repo` that has no `input_schema`, and with `exec:lint-repo` in `exposed`, fails with `capability exec:lint-repo is exposed and has no input_schema`.
  - The same config with an `input_schema` loads. The same config with `exec:lint-repo` not in `exposed` loads, also with no schema.
  - An `http` entry that is exposed and has no schema loads.
  - An `exposed` ID that no entry declares gives no error (the notice `unknown_id` covers it).
  - The error holds no `command` item and no schema value.
- [ ] T058 [P] [US4] Write failing test for `declared_caps` and the exposure of declared items in `tests/unit/test_declared.py` (FR-026, FR-027, SC-011):
  - `declared_caps` gives one core `Capability` per entry. The `id` is `<runtime>:<id>`. `role` is `item`, `open` false, `classified` false, `group` `None`. `tags` is `(<runtime>,)`. `declared_tags` come from the entry. `runtime`, `access`, and both schemas are copied.
  - `state_of` gives `owner-only` for a declared item with an empty `exposed` list. It gives `exposed` when its ID is in `exposed`, with `exposed_by` = `owner`. The clean rule never exposes it.
  - `exposure_notices` gives `unknown_id` for an ID `exec:nope` in `exposed`. It gives no `credential_exposed` for an exposed declared item.
  - `resolve_tags` with a tag map entry replaces the entry `tags` and keeps `(<runtime>,)` (FR-023).
  - The result holds no `command`, `url`, `token`, `env_allow`, or `timeout_s` value (the type has no such field).
  - The function does not change its input. The module is outside `core/`. It imports no `claude` adapter module.
- [ ] T060 [P] [US4] Write failing test for declared entries in the card in `tests/unit/test_card_build.py` (same file as T027 and T046; FR-029, SC-012, contracts/card.md rule 9):
  - An exposed declared item gives a card entry with `id`, `name`, `description`, `tags`, `access`, `input_schema`, and `output_schema`. An item with no schema has no schema key. An item with `access` `None` has no `access` key.
  - The entry holds no `runtime`, `command`, `url`, `token`, `env_allow`, or `timeout_s`. The test uses fake values for each of them and scans the card.
  - A declared item that is not exposed is not in `skills`.
  - A change of a schema changes the `hash`. A change of `command` or `url` in the config does not change the `hash` (they are not in the card).
  - `validate_card` returns a violation for a hand-made card whose schema has a URL, a token-like string, or a path in a string value (second wall).

### Implementation for User Story 4

- [ ] T055 [US4] Implement `check_schema` and `validate_schema` in `src/pipe/core/schema.py` (T054). The module uses only the standard library and stays near 50 lines (research.md D20)
- [ ] T057 [US4] Implement the validation of `capabilities` in `src/pipe/config.py` (T056; depends on T055; same file as T006 and 001 T005)
- [ ] T065 [US4] Add the `input_schema` rule for exposed `exec` entries to `validate_config` in `src/pipe/config.py` (T064; same file as T057, so it runs after T057)
- [ ] T066 [US4] Write a regression test for the card wire field names in `tests/unit/test_card_build.py` (same file as T060; FR-032, SC-015, decision E3). `build_card` output has the keys `bot_id`, `bot_user_id`, and `owner`. `validate_card` returns a violation for a card that has `agent_id`, `handle`, or `owner_id` in their place. No implementation task follows: the names already exist, and this test only guards them
- [ ] T059 [US4] Implement `declared_caps` in `src/pipe/declared.py` (T058; depends on T049, T057). The core `Capability` fields it fills are defined in T048 and T049
- [ ] T061 [US4] Add the optional entry fields `access`, `input_schema`, and `output_schema` to `build_card`, and the schema scan to `validate_card`, in `src/pipe/core/card.py` (T060; depends on T055; same file as T032, so it runs after T047)
- [ ] T062 [P] [US4] Write failing test in `tests/integration/test_declared_capabilities.py` with `FakeTransport` and a config that has one `exec` and one `http` entry (SC-011, SC-012):
  - `pipe capabilities` lists both as `owner-only`, with the types `exec` and `http`, and prints no command, URL, token, or environment name.
  - Start with both unexposed: the card has no entry for them. Add both IDs to `exposed`, start again: the same card is updated (same `ts`) and has both entries with their schemas.
  - Remove one ID: it leaves the card at the next start.
  - A scan of the card text and metadata finds no `://`, `xox`, `/Users`, `~/`, and none of the fake command, URL, token, or variable values. (The runtime tag `http` is not a URL and is allowed.)
  - The summary DM counts the declared items. A new declared item gives one new DM.
  - A config with a bad entry fails to load before any Slack call.
- [ ] T063 [US4] Add declared capabilities to the discovery step in `src/pipe/cli.py` and `src/pipe/adapter.py` (T062; depends on T014, T059, T061; same files as T015, T016, T037, T045): merge `declared_caps(config.capabilities)` with the `to_core` values before `render_list`, `build_card`, and `build_summary`

**Checkpoint**: All four user stories work.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T038 MANUAL — not run by make ci. Write the manual helper `tests/manual/load_probe.py` (about 20 lines): it builds a `PreparedLoad` for the current `exposed` set, runs the real `claude` with `build_cmd`, and prints the answer to a prompt that asks for one exposed skill. Then run quickstart section 3. Check: the exposed skill runs, a not-exposed skill is denied, only exposed MCP tools exist, a call of an exposed MCP tool is allowed by `mcp__<server>` (research.md A4), a command of the generated plugin runs (A5), and `~/.pipe/run` is empty afterwards
- [ ] T039 MANUAL — not run by make ci. Run quickstart section 2 on the real Slack workspace: scopes `pins:write`, `pins:read`, and `im:write` (check that `chat:write` is present), one summary DM and no DM on restart (research.md A7), one pinned card, update in place, deleted and unpinned card, 30 exposed skills for the metadata size (research.md A1, A2), the SC-005 time (list review and one exposure under 5 minutes), and the start-up time added by discovery and card sync (plan.md goal: under 5 seconds on 20 plugins)
- [ ] T040 MANUAL — not run by make ci. Run `pytest tests/unit tests/integration`, then the SC-003 scan on the live card (`http`, `xox`, `/Users`, `~/`). Confirm that `pipe doctor` (001) still passes five checks and that the 001 tests still pass

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependency.
- Foundational (Phase 2): needs Phase 1. It blocks all user stories.
- US1 (Phase 3): needs Phase 2.
- US2 (Phase 4): needs Phase 2. T023 needs T013 (`read_mcp_entries`). T025 needs T015, T016 (US1 wiring). T044 and T045 (US2 DM tasks) sit in Phase 5 because they need T034, T035, and T037.
- US3 (Phase 5): needs Phase 2. T032 needs T008 and T053. T037 needs T016 and T025 (same file `adapter.py`).
- Polish (Phase 6): needs all stories.

### Within Each User Story

- Test tasks come first and MUST fail before the implementation task.
- Pure functions in `src/pipe/core/` before the I/O code that calls them.
- Tasks that edit the same file are not marked [P]: `exposure.py` (T008, T021), `runtime_claude_exposure.py` (T051, T014), `card.py` (T031, T053, T032, T033, T047), `cli.py` (T015, T025), `adapter.py` (T016, T025, T037, T045, T047).
- Test-first pairs: T054 before T055. T056 before T057. T064 before T065. T058 before T059. T060 before T061. T062 before T063. T003 before T004. T005 before T006. T007 before T008. T011 before T013. T012 before T014 to T016. T017 before T021. T018 before T022. T019 before T023. T020 before T024. T026 before T031. T027 before T032. T028 before T033. T029 before T034. T030 before T035 to T037. T041 before T043. T042 before T044 and T045. T046 before T047. T048 before T049. T050 before T051. T052 before T053.
- IDs T054 to T066 (declared capabilities, Phase 5A) were added on 2026-11-26. T064 to T066 came with the second batch of owner decisions (constitution 1.3.0). They sit in Phase 5A, in file order. IDs T041 to T045 were added after the first numbering. They sit in Phase 4 (T041 to T043) and Phase 5 (T044, T045) in file order. IDs T046 and T047 (card `bot_user_id`) sit in Phase 5. IDs T048 to T051 (core `Capability`, adapter `classify` and `to_core`) sit in Phase 2. IDs T052 and T053 (`resolve_tags`) sit in Phase 5.

### Parallel Opportunities

- Phase 2: T003, T005, T007, T009, T010, T048, T050 together; then T049, then T004, T008, T051.
- US1 tests T011 and T012 together.
- US2 tests T017 to T020, T041, and T042 together; then T022 and T043.
- US3 tests T026 to T030, T046, and T052 together; then T034 beside T031.
- US3 can run beside US2 with another developer after Phase 2 (T037 waits for T025).

---

## Parallel Example: User Story 3

```text
# Launch all pure-function tests together:
Task: "Write failing test for sanitize_text and skills_hash in tests/unit/test_card.py"
Task: "Write failing test for build_card and validate_card in tests/unit/test_card_build.py"
Task: "Write failing test for decide_publish and pick_own_card in tests/unit/test_card_publish.py"

# Then the implementation in order (same file):
Task: "Implement sanitize_text and skills_hash in src/pipe/core/card.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Stop and validate: tests pass, then quickstart scenarios "1".
4. Demo `pipe capabilities`.

### Incremental Delivery

1. Add US2 (notices and load builder). Validate.
2. Add US3 (card). Validate. This gives the full M1 acceptance of the design brief.
3. Polish: manual checks on real `claude` and real Slack.

### Traceability

- FR-001: T011, T013. FR-002: T012, T014, T015, T016. FR-003, FR-004: T050, T051. FR-005: T007, T008, T018, T022, T027. FR-006: T005, T006 (only the local config changes `exposed`). FR-007, FR-008: T027, T032. FR-009: T026, T027, T030, T031, T032. FR-010: T026, T031. FR-011, FR-012: T028, T030, T033, T036. FR-013: T030, T036, T037. FR-014: T017, T021, T025, T030. FR-015: T007, T008, T050, T051, T027, T030. FR-016: T007, T008, T017, T018, T021, T022, T027, T030. FR-017: T007, T008, T017, T027, T030. FR-018: T007, T008, T017, T021, T027. FR-019: T041, T042, T043, T044, T045. FR-020: T029, T034, T041, T042, T043, T044. FR-021: T046, T047, T030. FR-022: T003, T011, T027, T030. FR-023: T003, T005, T006, T011, T027, T030, T048, T052, T053. FR-026: T056, T057, T058, T059, T062, T063. FR-027: T058, T059, T062. FR-028: T056, T057. FR-029: T060, T061, T062. FR-030: T054, T055, T056, T057. FR-024: T018, T022, T020, T024. FR-025: T048, T049, T050, T051, T004, T008, and the import-boundary test T071 of spec 003.
- SC-001: T030, T039. SC-002: T027, T030. SC-003: T026, T027, T030, T040. SC-004: T030, T039. SC-005: T039. SC-006: T042, T044, T045, T039. SC-007: T046, T047. SC-008: T003, T011, T027. SC-009: T030, T052. SC-010: T071 of spec 003. SC-011: T058, T062. SC-014: T064, T065. SC-015: T066. FR-031: T064, T065. FR-032: T066. SC-012: T060, T062. SC-013: T056.
- Design brief §12 (load into `--restricted` child): T018 to T020, T022 to T024, T038. These tasks build and test the load-set builder only. The wiring is in `ClaudeRuntime` and runs only when the run has capability IDs; the mention path sets none until spec 003. T020 guards this with a regression test.

---

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Verify that each test fails before you write the implementation.
- Do not commit from these tasks without an explicit owner request.
