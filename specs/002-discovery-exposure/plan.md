# Implementation Plan: Discovery and Exposure

**Branch**: `002-discovery-exposure` | **Date**: 2026-11-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-discovery-exposure/spec.md`

## Summary

At start, `pipe-adapter` reads the local Claude Code configuration (installed and enabled plugins, personal skills, slash commands, MCP server names, repos under `runtime.claude.repo_roots`). It shows the list with the exposure state to the owner (`pipe capabilities`, the adapter log, and one Slack DM when the summary changes). Pure functions decide the state. The `claude` adapter classifies each item and the core consumes the result: any MCP server and any skill that is not proven safe is `owner-only` until the owner lists its ID (or its plugin ID) in `exposed` in `~/.pipe/config.yaml`. A repo is listed only. The adapter builds one agent card (design brief §5.3) from the exposed items only, removes URLs, paths, and tokens, computes the sha256 hash of the skills list, and posts and pins the card in `#pipe-agents`. On later starts it updates the same card with `chat.update` only when the hash changes. The card also holds the `bot_user_id` of the bot (from `auth.test`), stable capability IDs in `skills[].id`, and tags (from the skill frontmatter and from the optional owner config map `tags`; the map wins). The plan also provides the load-set builder for a `claude -p --restricted` child (brief §12). The builder is part of the `claude` runtime adapter. It takes capability IDs as input. It makes a generated plugin with `--plugin-dir`, per-skill `--allowedTools` rules, and an exposed-only `--mcp-config`. These flags were checked with real runs. 002 does not load anything into a run. Specs 003 and 004 do. Details: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.15 (same as 001, research.md D1 of 001).

**Primary Dependencies**: `slack_bolt`, `pyyaml` (both from 001). `pyyaml` parses the YAML frontmatter of `SKILL.md` and command files and the config. Test-only: `pytest`. No new dependency (research.md D14). The schema subset validator is a small stdlib module, not the `jsonschema` package (research.md D20).

**Storage**: Files under `~/.pipe/` (JSON, atomic write): `state.json` gets the keys `bot_id`, `agents_channel_id`, `card`, `summary_hash`. A short-lived `~/.pipe/run/<run_id>/` holds the generated plugin and the MCP file during one run. The card itself lives in Slack. No database.

**Testing**: `pytest`. Pure functions have unit tests first: `validate_schema`, `check_schema`, `declared_caps`, `find_signals`, `classify`, `to_core` (`claude` adapter), `state_of`, `exposed_by`, `assign_ids`, `sanitize_tags`, `resolve_tags`, `exposure_notices`, `build_summary`, `decide_dm`, `sanitize_text`, `skills_hash`, `build_card`, `validate_card`, `decide_publish`, `pick_own_card`, `load_set`, `parse_frontmatter`. Discovery reads a fake directory tree built in `tmp_path` (fake plugins, skills, commands, `~/.claude.json` with fake secrets). The Slack side uses `FakeTransport` from 001 (extended). One stub-`claude` test checks the new command flags. A manual run with the real `claude` is in [quickstart.md](quickstart.md). No test calls real Slack or a real LLM.

**Target Platform**: macOS laptop (same as 001).

**Project Type**: Extension of the 001 CLI and background process (`pipe run`, new `pipe capabilities`).

**Performance Goals**: Discovery and card sync add less than 5 seconds to the adapter start on 20 plugins (SC-001 needs the card to be right after one start). The owner reviews the list and exposes one item in under 5 minutes (SC-005).

**Constraints**: No server, no database, no web UI. The card holds no URL, token, path, or config content. `claude mcp list` is not used (network, URLs). The adapter never edits settings files of the owner. `--restricted` stays on every run. No plain token in any file.

**Scale/Scope**: 3 to 6 developers. About 20 plugins, 100 skills, 15 MCP servers per laptop. One card per agent.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.3.0 (second batch: an exposed `exec` capability has an `input_schema`; declared capabilities are `read` only; `http` uses `https`, except for `localhost` and `127.0.0.1`: PASS, see FR-028, FR-031).

| Principle | Pre-research | Post-design | Note |
|---|---|---|---|
| I. No Server in the MVP | PASS | PASS | Local files and Slack only. The card is a Slack message. `state.json` is a local cache. |
| II. The Owner Controls the Agent | PASS | PASS | Only the owner edits `exposed` and `tags` in the local config (FR-006, FR-023). The adapter never edits the settings of the owner. |
| III. Discovered Is Not Exposed | PASS | PASS | This feature implements it. Every MCP server, repo, and plugin item, every declared (`exec`, `http`) capability, and every skill or command not proven safe, is `owner-only`. `classify` (`claude` adapter) is conservative (research.md D3). Only `exposed` IDs (or skills of an exposed plugin) or proven-safe items reach the card. |
| IV. Every Change Goes Through an MR | PASS (not in scope) | PASS | No repo write. The generated plugin lives under `~/.pipe/run/`. |
| V. Thread Content Is Untrusted Input | PASS | PASS | 002 reads no thread content. It reads only its own card (`pick_own_card` filters by own `bot_id`). Trust in other cards is spec 003. |
| VI. Runtime-Agnostic Contract | PASS | PASS | The load set is a command-line concern of the `claude` runtime adapter (`runtime_claude_loadset.py`, `runtime_claude_load.py`, `runtime_claude.py`). `RuntimeInput` is unchanged. The runtime still gets no `hop`, trust, or Slack data. See [contracts/runtime-load.md](contracts/runtime-load.md). |
| VII. Business Rules Are Pure Functions | PASS | PASS | `classify`, `to_core`, `state_of`, `exposed_by`, `exposure_notices`, `resolve_tags`, `build_card`, `validate_card`, `decide_publish`, `load_set`, `build_summary`, `decide_dm` are pure and tested first, without Slack and without an LLM. |
| VIII. Reuse Before Build | PASS | PASS | Reuses 001 `scrub`, `state`, `config`, `transport_slack`, `ports`, `fakes`, the `chat.update` pattern, the `claude -p` builder, and the CLI dispatcher. No wiz-review change. |
| IX. Small Dependencies | PASS | PASS | No new dependency. `pyyaml` (already allowed) parses frontmatter. |
| X. STE for All Written Artifacts | PASS | PASS | All artifacts use STE. |
| XI. Core Is Capability-, Runtime-, and Transport-Agnostic | PASS | PASS | The card gives the core stable capability IDs (`skills[].id`), tags, and `bot_user_id`. The Claude Code rules sit in the `claude` runtime adapter: `runtime_claude_capability.py` (frontmatter, credential signs, IDs), `runtime_claude_exposure.py` (the safe tool set, `mcp__`, `classify`, `to_core`), `runtime_claude_loadset.py`, `runtime_claude_load.py`, and `runtime_claude.py`. The adapter classifies and gives the core a `Capability` with the result. The core modules (`core/capability.py`, `core/exposure.py`, `core/card.py`, `core/summary.py`) use IDs, roles, and the class only. No core module imports an adapter module. The import-boundary test of spec 003 (T071) covers these modules and `core/schema.py`. A declared capability (`exec`, `http`) enters the core as a generic `Capability` (`declared.py`, outside `core/`). The core sees `runtime` as an opaque string. The card is published through the `Transport` port. |

Technology and Security Constraints: Keychain for tokens (no change). Scrub before post (PASS: `sanitize_text` uses `scrub`). "A task from a non-owner never gets `owner-only` tools" (PASS: 002 passes no load set to any run; the load builder only adds exposed items). `hop` limit (not in scope). "Agent cards MUST NOT contain MCP URLs, tokens, local paths, or config content" (PASS: `sanitize_text` plus `validate_card`, tests T014 to T017, SC-003 scan).

**Result**: PASS. No deviation. No Complexity Tracking row.

The decisions in "Design decisions" below do not conflict with the constitution.

## Design decisions

The owner of the project settled five design questions and three more decisions on 2026-11-26. Each decision is in force.

- **Q1 = (b). Plugin and repo entries.** An `exposed` entry with a plugin ID exposes all skills of that plugin. Each skill still goes through the credential check. A credential-backed skill of an explicitly exposed plugin is exposed (explicit expose wins, Q4), and the owner gets a notice. A repo entry is listed only. A repo is always `owner-only` and never enters the card. Repo work belongs to spec 004.
- **Q2 = (a). No load in 002.** 002 provides only the load-set builder (`pipe-exposed` plugin, `--plugin-dir`, `--allowedTools "Skill(pipe-exposed:<name>)"`, `--mcp-config` with `--strict-mcp-config`). 002 loads nothing into a run. Specs 003 and 004 pass capability IDs and an access level. The `claude` runtime adapter builds the load set.
- **Q3 = (a). Clean skills.** A clean skill (all `allowed-tools` in the safe set, no credential signs) is exposed with no owner action. There is no `hidden:` key.
- **Q4 = (a). Later credential change.** An item that the owner exposed by name or by plugin ID stays exposed when it becomes credential-backed, and the owner gets a notice. An item exposed only by the clean rule leaves the card.
- **Q5 = (a)+(b). Owner view.** The owner sees the list and the notices in `pipe capabilities` and in the adapter log. At adapter start, the adapter also sends the owner one Slack DM with a summary (counts and all notices). It sends the DM only when the summary differs from the last one sent. A hash of the last summary is in `~/.pipe/state.json`. New scope: `im:write` (`chat:write` is already present from 001).
- **Core and adapter split (2026-11-26).** The Claude Code rules (frontmatter, the safe tool set, `mcp__`, credential signs, capability types, `classify`) are in the `claude` adapter. The core keeps agnostic types and rules (ID, role, class, `state_of`, `exposed_by`, notices, card, summary). Research D17.
- **Tag sources (2026-11-26).** The tags come from the frontmatter and from the owner config map `tags`. The map wins for a capability that has an entry. Research D18.
- **Card trust (2026-11-26, confirmed).** Readers of the card require that the message `user` equals `bot_user_id` when it is present, and that the card with the lower `ts` keeps a duplicate `bot_user_id`. Spec 003 enforces both checks (task T007 of 003). 002 only publishes `bot_user_id`.
- **Pass 1 of 2026-11-26, second batch (constitution 1.3.0).**
  - **E1. Exposed `exec` needs an `input_schema`.** The config load fails without it (FR-031, SC-014). Tasks: T064, T065.
  - **E2. Declared `exec` and `http` are `read` only. `http` uses `https`, except for `localhost` and `127.0.0.1`.** The rules were in FR-028. The owner confirmed them. Tasks: T056, T057 (the tests state "confirmed").
  - **E3. Card wire field names stay.** `bot_id`, `bot_user_id`, `by`, and `owner` keep their names (FR-032, SC-015). Task: T066.

## Project Structure

### Documentation (this feature)

```text
specs/002-discovery-exposure/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── card.md
│   ├── runtime-load.md
│   └── cli.md
└── tasks.md             # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

New files are marked `+`. Changed 001 files are marked `~`.

```text
src/pipe/
├── core/                            # PURE functions only
│   ├── capability.py        +       # Capability (core, agnostic; fields runtime, access, input_schema, output_schema, classified), Notice, sanitize_tags
│   ├── schema.py            +       # validate_schema(instance, schema) -> errors ; check_schema(schema) -> errors (supported subset, stdlib, about 50 lines)
│   ├── exposure.py          +       # state_of, exposed_by, exposure_notices, render_list (agnostic; consume the class from the adapter)
│   ├── summary.py           +       # Summary, build_summary, decide_dm
│   └── card.py              +       # sanitize_text, skills_hash, resolve_tags, build_card (with bot_user_id and the tag map), validate_card, decide_publish, pick_own_card
├── runtime_claude_capability.py +   # `claude` adapter, pure: ClaudeCapability, parse_frontmatter, find_signals, assign_ids
├── runtime_claude_exposure.py +     # `claude` adapter, pure: SAFE_TOOLS, classify, to_core (ClaudeCapability -> Capability)
├── declared.py              +       # pure: declared_caps(entries) -> list[Capability] (declared exec and http capabilities; not a core module)
├── runtime_claude_discovery.py +    # `claude` adapter, I/O: reads ~/.claude files, runtime.claude.repo_roots; returns list[ClaudeCapability] and MCP entries
├── card_sync.py             +       # sync_card(slack, state, card): post, update, pin, recover
├── owner_summary.py         +       # send_summary(slack, state, owner, summary): one DM when the hash differs
├── runtime_claude_loadset.py +      # `claude` adapter, pure: LoadSet, load_set(caps, exposed, capability_ids)
├── runtime_claude_load.py   +       # `claude` adapter: prepare(load, run_dir, mcp_entries): generated plugin, mcp.json (builder only; no 002 caller)
├── config.py                ~       # validate exposed, tags, description, agents_channel, capabilities (declared)
├── ports.py                 ~       # Transport: update_message, pin, list_pins, history, send_dm(user_id, text); post_message(metadata)
├── transport_slack.py              ~       # the new Transport methods over slack_sdk
├── runtime_claude.py        ~       # build_cmd(..., prepared=None) adds the load flags (default None; 002 passes None)
├── adapter.py               ~       # at start: discovery, log list, sync_card, send_summary (errors are logged)
└── cli.py                   ~       # `pipe capabilities`; `pipe run` start-up

tests/
├── unit/                            # test_runtime_claude_capability.py, test_capability.py, test_exposure.py, test_runtime_claude_exposure.py,
│                                    # test_schema.py, test_declared.py, test_card.py, test_card_tags.py, test_card_build.py, test_card_publish.py, test_summary.py, test_runtime_claude_loadset.py, test_runtime_claude_discovery.py, test_runtime_claude_load.py
│                                    # (+ changes to test_config.py, test_state.py, test_runtime_claude.py)
├── fakes.py                 ~       # FakeTransport: update_message, pin, list_pins, history with metadata; build_claude_tree(tmp_path)
├── integration/                     # test_card_sync.py, test_capabilities_cli.py, test_owner_summary.py
└── manual/load_probe.py     +       # manual check with the real claude (quickstart section 3)
```

**Structure Decision**: Single project, same layout as 001. The agnostic rules sit in `core/` as pure functions. The Claude Code rules sit in the `claude` adapter files (`runtime_claude_*.py`), also as pure functions where possible. All file and Slack access sits outside `core/`.

## Complexity Tracking

No constitution deviation. No row.
