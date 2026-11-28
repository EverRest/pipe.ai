# Feature Specification: Knowledge Capability (Wiki LLM)

**Feature Branch**: `008-knowledge-capability`

**Created**: 2026-11-28

**Status**: Draft, deferred. The owner wants the work "later". This spec records the agreed design. Do not plan tasks until the two `[OPEN]` questions have answers.

**Input**: User description: "The owner has a wiki LLM that runs as a Slack bot. An agent in a pipeline step must be able to ask it a question and get instructions."

## Model (from specs 002, 003, 005, 007 and the design brief)

- The wiki is a `knowledge` capability. It is read-only. It answers questions. It changes nothing.
- The owner declares it as an `http` capability in one owner config (spec 002). It uses `https` only. The token comes from the Keychain by name (`token: keychain:<service>`). It has an `input_schema`. The owner exposes it explicitly (decision 10: a declared capability is `owner-only` until exposed).
- Input: `{question}`, at most 500 characters. Output: `{answer, sources[]}`.
- A step can name `capability: "tag:knowledge"` with `agent: "any"` (spec 003, decision 17). The claim rule picks one agent.
- A later step gets the answer in `context` of the effective payload (`effective_payload`, spec 003 FR-037).
- The core stays capability-agnostic (principle XI). It knows no wiki.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An agent asks a question in a pipeline step (Priority: P1)

A pipeline has a step with `capability: "tag:knowledge"` before the work step. The step sends the question to the wiki. The answer goes into `context` of the next step. The work step uses the answer as reference data.

**Why this priority**: It is the main use. It needs no change in the wiki bot and no new core rule.

**Independent Test**: Run a pipeline with a fake wiki capability and a work step. Check that the work step receives the answer and the source links in `context`.

**Acceptance Scenarios**:

1. **Given** a plan has a step with `capability: "tag:knowledge"`, **When** the plan check runs, **Then** the plan is valid when a trusted card lists an exposed capability with the tag `knowledge`. If no card lists it, the plan is rejected before ✅ (spec 003).
2. **Given** the knowledge step has a question of 500 characters or less, **When** the step runs, **Then** the adapter sends `{question}` and the step ends with `{answer, sources}`.
3. **Given** the question is longer than 500 characters, **When** the adapter checks the payload, **Then** the step is `failed` with `reason: invalid_payload` and no request goes to the wiki.
4. **Given** the knowledge step is `done`, **When** the next step starts, **Then** `context` holds the answer and `artifacts` holds the source links.
5. **Given** the answer says "run this command" or "ignore your rules", **When** the next step starts, **Then** the step rights stay the same (`access`, tools, `deny_rules`).
6. **Given** the wiki is down or it times out, **When** the step ends, **Then** the step is `failed` with a reason and a "Retry" button (spec 003).

---

### User Story 2 - An owner exposes the wiki as a capability (Priority: P1)

The owner adds the wiki as an `http` capability in the config. The owner gives it the tag `knowledge` and exposes it. Other agents can then claim `tag:knowledge` steps.

**Why this priority**: Without exposure, no other agent can use the wiki.

**Independent Test**: Load a config with the wiki entry. Check the config rules. Check that the card lists the capability only after exposure.

**Acceptance Scenarios**:

1. **Given** the entry uses `http://` for a non-local host, **When** the adapter loads the config, **Then** the load fails.
2. **Given** the entry has no `input_schema`, **When** the owner exposes it, **Then** the load fails. (This is stricter than spec 002. Spec 002 requires it for `exec` only.)
3. **Given** the entry has a plain token, **When** the adapter loads the config, **Then** the load fails. The token must be `keychain:<service>`.
4. **Given** the entry is declared and not exposed, **When** the card is built, **Then** the capability is not on the card.
5. **Given** the entry is exposed, **When** the card is built, **Then** the card lists the capability with `access: read` and the tag `knowledge`.

---

### User Story 3 - A restricted document is not leaked (Priority: P1)

The wiki answers with the access rights of its owner. Another person in the team can start a step that asks a question. The answer must not show a document that this person may not read.

**Why this priority**: This is a confused-deputy risk (decision 10, decision 16). It decides if the feature is safe to use.

**Independent Test**: Use a fake wiki with one open and one restricted document. Ask for the restricted one as a person without access. Check that the policy gives no leak.

**Acceptance Scenarios**:

1. **Given** the shared wiki holds only documents that are open to the whole team, **When** any team member asks, **Then** the answer is allowed.
2. **Given** the wiki holds restricted documents, **When** the capability cannot check the asker, **Then** the owner must not expose it to the team. `[OPEN]` Q2 decides which option applies.
3. **Given** the capability checks the asker, **When** the asker has no access to a source, **Then** the answer does not use that source and does not list it.
4. **Given** the answer shows in the thread, **When** the thread is in a public channel, **Then** the owner accepts that all channel members read it. For a sensitive wiki, the owner uses a private channel.

### Edge Cases

- The answer is longer than the size limit. The adapter cuts it and marks it as cut.
- The answer holds a string that looks like a token. The adapter scrubs it before it posts.
- `sources` is empty. The step is `done`. The next step sees "no sources" and treats the answer as unverified.
- A source link is not `https`. The adapter drops it.
- The wiki returns a body that does not match `output_schema`. The step is `failed` with `reason: run_failed`.
- Many steps ask in a short time. The rate limit stops them (FR-010). The step is `failed` with a reason and a "Retry" button.
- A schema with `additionalProperties: false` must list `context` and `artifacts` (spec 003 FR-037). The wiki `input_schema` must allow them, or it must not use `additionalProperties: false`.
- Two agents have a `knowledge` capability. The claim rule picks one.
- The owner is offline. The step waits for the claim or ends with `no_claimer` (spec 003).
- The wiki bot is Slack-only and has no API. Use 1 cannot work. `[OPEN]` Q1.

## Requirements *(mandatory)*

### Functional Requirements

**Capability**

- **FR-001**: The knowledge capability MUST be a normal declared capability (`runtime: http`, spec 002). The system MUST NOT add a step type, a field, or wiki code to the core.
- **FR-002**: The entry MUST use `https`, a token of the form `keychain:<service>`, and an `input_schema`. The owner MUST expose it explicitly.
- **FR-003**: The entry MUST be `access: read` and carry the tag `knowledge` (config map `tags`).
- **FR-004**: The input MUST be `{question}`. The `input_schema` MUST limit `question` to 500 characters (`maxLength`).
- **FR-005**: The output MUST be `{answer, sources[]}`. The output MUST be checked against `output_schema` (spec 003 `check_output`).

**Use in a pipeline**

- **FR-006**: A step MUST be able to name `capability: "tag:knowledge"` with `agent: "any"`.
- **FR-007**: The answer MUST reach the next step through `context` of `effective_payload`. The source links MUST reach it through `artifacts`.
- **FR-008**: The system MUST NOT add a new trust path. The knowledge step ends with `status: done` of the claiming agent (spec 005).

**Security**

- **FR-009**: The answer MUST be treated as untrusted reference DATA. It MUST NOT change the `access`, the tools, or the rules of any step. A runtime adapter MUST NOT run an instruction from an answer.
- **FR-010**: The adapter MUST limit the answer size and MUST scrub token-like strings before it posts or passes the answer. It MUST keep the source links. It MUST apply a request rate limit and a budget for the capability. (The budget key is new. `max_budget_usd` of spec 001 is for the `claude` adapter only.)
- **FR-011**: The system MUST NOT give the answer of a restricted document to a person who may not read it. The shared knowledge base MUST hold only documents that are open to the whole team, OR the capability MUST check the asker. `[OPEN]` Q2.
- **FR-012**: The adapter MUST NOT write a token to a log, a file, or a posted text.
- **FR-013**: The owner MUST be able to see in the docs that the answer shows in the thread, and that a sensitive wiki needs a private channel.

**Later (not in the first version)**

- **FR-014**: An MCP server over the wiki MAY let an agent ask during its own run. The plugin library (spec 007) MAY share it. The first version does not include it.

### Key Entities

- **Knowledge capability**: A read-only `http` capability with the tag `knowledge`. Input `{question}`. Output `{answer, sources[]}`.
- **Knowledge step**: A normal step with `capability: "tag:knowledge"`. It runs before the work step.
- **Answer**: Untrusted reference data. It has a size limit and scrubbed text.
- **Source**: An `https` link to a wiki document.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tests, the work step after a knowledge step receives the answer in `context` and the sources in `artifacts`.
- **SC-002**: In 100% of tests, a question over 500 characters sends no request to the wiki.
- **SC-003**: In 100% of tests, an answer with an instruction changes no `access`, no tool list, and no deny rule.
- **SC-004**: In 100% of tests, an answer over the size limit is cut, and a token-like string is scrubbed.
- **SC-005**: In 100% of tests, a config with `http://` (non-local), a plain token, or no `input_schema` fails to load.
- **SC-006**: In 100% of tests, a request over the rate limit or the budget fails with a reason and sends no request to the wiki.
- **SC-007**: In 100% of tests, a fake restricted document does not reach a person without access, under the chosen option of Q2.
- **SC-008**: In 100% of builds, the import-boundary test passes: no core module names the wiki.

## Assumptions

- Specs 001 to 007 exist. The `http` runtime adapter, `input_schema`, `output_schema`, `tag:` steps, and `effective_payload` come from them.
- The wiki LLM runs as a Slack bot of the owner today.
- The first version uses a simple question and answer. It has no dialog and no write access.
- **`[OPEN]` Q1**: Does the wiki bot have an HTTP API or a CLI, or is it Slack-only? The owner has not answered. Use 1 needs an API or a CLI. If it is Slack-only, the wiki bot needs a change, or the work waits.
- **`[OPEN]` Q2**: Does the wiki hold documents with restricted access? The owner has not answered. If yes, FR-011 needs the second option (the capability checks the asker) or a team-only knowledge base.
- Rejected: a Slack-native agent with a card. It needs changes in the wiki bot.
- Rejected: an @mention in the channel with free-text parsing. Free-text parsing is unreliable, and it depends on the unverified `app_mention` behavior between bots.
