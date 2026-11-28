# Implementation Plan: Knowledge Capability (Wiki LLM)

**Branch**: `008-knowledge-capability` | **Date**: 2026-11-28 | **Spec**: [spec.md](spec.md)

**Status**: Draft, deferred. No `tasks.md` exists. Tasks come after the two open questions (Q1, Q2) have answers.

## Summary

The owner has a wiki LLM that runs as a Slack bot. Agents must ask it questions. The plan uses what exists: a declared `http` capability (spec 002), a `tag:knowledge` step (spec 003), and `context` in `effective_payload`. The core gets no new code.

## Design decisions

1. **Capability, read-only.** The wiki is a `knowledge` capability. It is declared as `http` in one owner config. Rules: `https` only, `token: keychain:<service>`, `input_schema` required, explicit exposure.
2. **Contract.** Input `{question}`, max 500 characters. Output `{answer, sources[]}`.
3. **Use 1 (first).** A step `tag:knowledge` runs before the work step. The answer goes into `context` of the next step.
4. **Use 2 (later).** An MCP server over the wiki lets an agent ask during its own run. The plugin library (spec 007) can share it.
5. **Rejected: a Slack-native agent with a card.** It needs changes in the wiki bot.
6. **Rejected: an @mention in the channel with free-text parsing.** Free-text parsing is unreliable. It depends on the unverified `app_mention` behavior between bots.
7. **Security.**
   - The answer is untrusted reference data. It never changes step rights.
   - Limit the answer size. Scrub tokens. Keep the source links.
   - Confused deputy: the wiki answers with the rights of its owner. The shared knowledge base holds only documents that are open to the whole team, OR the capability checks the asker.
   - The answer shows in the thread. Use a private channel for a sensitive wiki.
   - Add a request rate limit and a budget.

## Risks

- Q1 is open. If the wiki bot is Slack-only, use 1 is blocked.
- Q2 is open. If the wiki holds restricted documents, the team-wide exposure is unsafe without an asker check.
- Prompt injection through the answer. The limit is that an answer is data and has no power over rights.
- Cost. A step that asks many questions spends the owner's quota. The rate limit and the budget cover it.
- Channel exposure. The thread shows the answer to all channel members.

## Not decided

- Q1: HTTP API, CLI, or Slack-only.
- Q2: Restricted documents in the wiki, and the option to use (team-only base, or an asker check).
- The size limit of the answer, the rate limit value, and the budget key name.
- How the asker check works (for example a per-asker token, or the wiki filters by asker ID).
- How `{answer, sources}` maps to the wrapper output (`text`, `artifacts`, `data`) of spec 005 `contracts/slow-capability.md`. The `http` adapter output rule may need a small clarification.

## Contradictions and gaps found in existing specs

- Spec 002 requires `input_schema` for an exposed `exec` capability only. This plan requires it for an exposed `http` knowledge capability too. This is a stricter rule for one capability, set by the owner config. A decision is needed: a general rule for `http`, or a check for the tag.
- `max_budget_usd` (spec 001) is a `claude` adapter key. No budget key exists for `http`. Spec 003 FR-034 and the `http` adapter need one.
- No spec has a request rate limit. Spec 005 DQ4 says there is no rate cap for a leaked trigger token.
- No spec limits the size of a `context` entry. The answer size limit is new.
- A schema with `additionalProperties: false` must list `context` and `artifacts` (spec 003 FR-037). The wiki `input_schema` must follow this.

## First tasks (after Q1 and Q2 have answers)

- Answer Q1 and Q2. Pick the Q2 option.
- Write a failing test for the config rules: `https`, Keychain token, `input_schema`, exposure.
- Write a failing test for the 500-character limit (`maxLength`).
- Write a failing test: an answer with an instruction changes no step rights.
- Write a failing test: size limit, token scrub, source links kept.
- Add the rate limit and the budget to the `http` adapter.
- Map `{answer, sources}` to the step result and `context`.
- Implement the Q2 option (team-only base check, or asker check).
- Add an example config entry for the wiki. Add a security note in the docs.
- Later task: add the tag `knowledge` to the vocabulary (`flows/tags.yaml`, owned by spec 006).
- Later task: add a `context` step to the flow templates that need it (spec 006).
- Later task: the MCP server over the wiki and the share through spec 007.
