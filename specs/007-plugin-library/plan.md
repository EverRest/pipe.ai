# Implementation Plan: Shared Plugin Library

**Branch**: `007-plugin-library` | **Spec**: [spec.md](spec.md)

## Summary

The library is a git repository in marketplace format. It lives outside this repository (`pipe-library`). This repository gets one change: the adapter treats items of a library marketplace as `owner-only`. Slack only announces releases.

## Layout (library repository)

```
.claude-plugin/marketplace.json
plugins/<name>/.claude-plugin/plugin.json
plugins/<name>/skills/<skill>/SKILL.md
plugins/<name>/{commands,agents,hooks,evals}/   (optional)
plugins/<name>/README.md
CODEOWNERS
.gitlab-ci.yml
README.md
```

## CI checks

1. `claude plugin validate --strict .` (marketplace).
2. `claude plugin validate --strict plugins/<name>` for each plugin.
3. `claude plugin eval` for each plugin that has `evals/`.
4. Secret scan: `grep` for `xox`, `glpat-`, `BEGIN PRIVATE KEY`.
5. Tag check (on a tag only): the name is `<plugin>--v<version>` and the version equals `plugin.json`.
6. Release note (on a tag only): post to `#pipe-library`. See "Slack announcement".

## The adapter rule

- `config.py`: new key `library_marketplaces` (list of short names, default `[]`).
- `runtime_claude_capability.py`: `ClaudeCapability.marketplace` (from the plugin key).
- `runtime_claude_discovery.py`: sets `marketplace` on plugin items and plugin MCP entries.
- `runtime_claude_exposure.py`: `classify(cap, library)` and `to_core(cap, library)` return `owner-only` for a library item. This check runs before the clean rule.
- `capset.py`, `runtime_claude_loadset.py`, `runtime_claude_request.py`: pass `library_marketplaces` to `to_core`.
- The core is unchanged. It sees only `open=False`. An entry in `exposed` still exposes the item (`exposed_by` in the core).

## Slack announcement

- The CI job on a tag posts one line to `#pipe-library`: plugin, version, tag.
- The job uses a CI variable for the webhook. The repository holds no webhook.
- The post is optional. A failure does not fail the release.
- The adapter does not read `#pipe-library`.

## Risks

- A library plugin changes after the owner exposed it. Mitigation: pin the version, keep auto-update OFF, review by CODEOWNERS.
- A plugin author puts a secret in an MCP config. Mitigation: the secret scan, FR-009, and the `owner-only` default.
- The plugin key format changes. Mitigation: no `@` means no marketplace, so the item is not a library item. A test covers this. The owner can then list the item in `exposed` or leave it `owner-only`.
- The grep scan misses a secret form. Mitigation: it is a first filter. Review is the main control.

## Design decisions

- DQ1: The library is a git repository, not Slack. Slack announces releases only.
- DQ2: Layout as above. CODEOWNERS and a CI file are required.
- DQ3: Lifecycle: write, `claude plugin validate`, MR, CODEOWNERS approval, tag by `claude plugin tag` (`<plugin>--v<version>`), install `<plugin>@<marketplace>` with a pinned version.
- DQ4: Auto-update stays OFF for the library marketplace.
- DQ5: MCP configs in a library plugin hold no secrets. Credentials stay per person.
- DQ6: Skills, commands, and MCP servers from a library marketplace are `owner-only` by default. The owner exposes one in `exposed`. The clean rule of spec 002 does not apply, because the code belongs to other people.

## Constitution Check

- III: library items are `owner-only` until the owner exposes them. Pass.
- IV: every plugin change goes through an MR with a CODEOWNERS approval. Pass.
- VII: the rule is a pure function (`classify`). Tests come first. Pass.
- IX: no new dependency. Pass.
- X: specs use STE. Pass.
- XI: the core has no marketplace code. Pass.
