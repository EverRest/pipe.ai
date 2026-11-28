# Feature Specification: Shared Plugin Library

**Feature Branch**: `007-plugin-library`

**Status**: Draft

**Input**: A team keeps its Claude Code plugins in one git repository. Each owner installs plugins from it. A plugin from the library never becomes visible to other agents without the owner's decision.

## Model

- The library is a git repository in Claude Code marketplace format. It is not a Slack feature.
- The library marketplace has the name `pipe-library`. A plugin ID is `<plugin>@<marketplace>`.
- The adapter already finds installed plugins, skills, commands, and MCP servers (spec 002).
- Spec 002 FR-015 exposes a clean skill with no owner action. Spec 007 limits this rule (FR-010).
- Slack only announces releases in the channel `#pipe-library`. Slack holds no plugin.
- Constitution principle III (discovered is not exposed) and principle XI (core is agnostic) apply. See `.specify/memory/constitution.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Publish a plugin (Priority: P1)

An author writes a plugin. The author validates it, opens an MR, and gets an approval. A release tag publishes the version.

**Why this priority**: Without a publish path, the library has no content.

**Independent Test**: Make a plugin in the skeleton. Run `claude plugin validate`. Run the CI checks on a copy that holds a fake secret. The checks must fail.

**Acceptance Scenarios**:

1. **Given** a new plugin directory, **When** the author runs `claude plugin validate`, **Then** the command reports no error.
2. **Given** an MR, **When** the CI runs, **Then** it validates the marketplace and each plugin, and it scans for secrets.
3. **Given** the MR changes `plugins/<name>/`, **When** the MR is ready, **Then** a CODEOWNERS reviewer of that path must approve it.
4. **Given** the MR is merged, **When** the author runs `claude plugin tag`, **Then** the tag `<plugin>--v<version>` exists and the version equals the one in `plugin.json`.
5. **Given** a release tag, **When** the CI runs on the tag, **Then** the CI posts a release note in `#pipe-library`.

---

### User Story 2 - Install and pin (Priority: P1)

An owner adds the library marketplace and installs a plugin at a fixed version. The version changes only when the owner updates by hand.

**Why this priority**: Other people's code runs on the owner's laptop. The owner must control the version.

**Independent Test**: Read `README.md` of the skeleton. Follow the steps with a local copy. Check the installed version.

**Acceptance Scenarios**:

1. **Given** the marketplace URL, **When** the owner adds the marketplace, **Then** auto-update for it is OFF.
2. **Given** a release tag, **When** the owner installs `<plugin>@pipe-library`, **Then** the installed version equals the tag version.
3. **Given** a new release, **When** the owner reads the note in `#pipe-library`, **Then** the owner updates by hand. Nothing updates by itself.

---

### User Story 3 - Library items are owner-only (Priority: P1)

The owner lists `pipe-library` in `library_marketplaces`. Skills, commands, and MCP servers of library plugins stay `owner-only`, also when they look clean. The owner exposes one item by listing it in `exposed`.

**Why this priority**: The items are other people's code. A silent exposure would share that code under the owner's identity (principle III).

**Independent Test**: Run `pytest tests/unit/test_runtime_claude_exposure.py tests/integration/test_adapter_capabilities.py`.

**Acceptance Scenarios**:

1. **Given** a clean skill from a library marketplace, **When** the adapter classifies it, **Then** it is `owner-only` and it is not in the card.
2. **Given** the same skill ID is in `exposed`, **Then** it is exposed.
3. **Given** a clean skill from another marketplace, **Then** it stays exposed by the clean rule.
4. **Given** `library_marketplaces` is empty, **Then** nothing changes.
5. **Given** a step asks for a library skill that is not exposed, **Then** the runtime does not load it and denies it by name.

---

### Edge Cases

- A plugin is installed from a library marketplace and from another one with the same plugin name. The IDs differ by the marketplace key. Each item gets its own state.
- The plugin key has no `@`. The marketplace is unknown. The item is not a library item.
- The config value is not a list or has a bad name. The config load fails. The error names the key `library_marketplaces`. It never shows the value.
- A library plugin has an MCP config with a token. The CI secret scan fails. The adapter keeps the MCP server `owner-only`.
- The tag version differs from `plugin.json`. The CI tag check fails.
- A plugin has an `evals/` directory. The CI runs `claude plugin eval` for it. Without the directory, the CI skips the job.
- The Slack post fails. The release stays valid. The tag is the release.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST be a git repository with `.claude-plugin/marketplace.json` and `plugins/<name>/.claude-plugin/plugin.json`.
- **FR-002**: Each plugin MUST have at least one `skills/<skill>/SKILL.md`. It MAY have `commands/`, `agents/`, `hooks/`, and `evals/`.
- **FR-003**: Each plugin MUST have a `README.md` and a `version` in `plugin.json`.
- **FR-004**: The repository MUST have a `CODEOWNERS` file. A reviewer of the path MUST approve each MR (principle IV).
- **FR-005**: The CI MUST run `claude plugin validate` on the marketplace and on each plugin.
- **FR-006**: The CI MUST run `claude plugin eval` for a plugin only if it has an `evals/` directory.
- **FR-007**: The CI MUST fail when a file holds `xox`, `glpat-`, or `BEGIN PRIVATE KEY`.
- **FR-008**: A release MUST be a git tag `<plugin>--v<version>` made by `claude plugin tag`. The CI MUST fail when the tag version differs from `plugin.json`.
- **FR-009**: A plugin MUST NOT hold a secret. An MCP config in a plugin MUST NOT hold a credential. Credentials stay per person.
- **FR-010**: The config MUST accept `library_marketplaces`: a list of names (letters, digits, `-`, `_`; 1 to 64 characters). The default is `[]`. An error MUST name the key and MUST NOT show the value.
- **FR-011**: Discovery MUST record the marketplace of each plugin item. The marketplace is the part after `@` in the plugin key.
- **FR-012**: A skill, command, or MCP server of a plugin from a marketplace in `library_marketplaces` MUST be `owner-only`, also when it is clean. The clean rule of spec 002 FR-015 MUST NOT apply to it.
- **FR-013**: An entry in `exposed` MUST expose a library item (spec 002 explicit exposure).
- **FR-014**: The `owner-only` state MUST apply to the card, the capability list, the load set, and the tool deny list.
- **FR-015**: The core MUST NOT contain the word `marketplace`. Only the runtime adapter MAY know it (principle XI).
- **FR-016**: Auto-update MUST stay OFF for the library marketplace. The README MUST say this.
- **FR-017**: A release MUST be announced in `#pipe-library` with the plugin, the version, and the tag. The announcement is not a trust input and holds no secret.

### Key Entities

- **Library**: the git repository.
- **Library plugin**: a plugin directory under `plugins/`.
- **Release**: a tag `<plugin>--v<version>`.
- **Library marketplace**: a marketplace name in `library_marketplaces`.

## Success Criteria *(mandatory)*

- **SC-001**: `claude plugin validate` passes on the marketplace and on each plugin of the skeleton.
- **SC-002**: A clean library skill is never in a card unless it is in `exposed` (unit and integration tests).
- **SC-003**: With `library_marketplaces: []`, all tests of specs 001 to 006 pass without change.
- **SC-004**: The import-boundary test finds no marketplace word in `src/pipe/core/`.
- **SC-005**: The CI fails on each of: a fake `xox` token, a fake `glpat-` token, a fake private key header, and a wrong tag version.

## Assumptions

- The team uses GitLab. The CI file is `.gitlab-ci.yml`. Another CI needs a port of the same checks.
- The `claude` CLI runs in the CI image.
- Plugin keys have the form `<name>@<marketplace>`.
- Owners trust the CODEOWNERS review, but still decide what they share.
- URLs and owners in the skeleton are placeholders: `<GIT_URL>`, `<OWNER>`.
