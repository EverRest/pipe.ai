<!--
Sync Impact Report
Version change: 1.2.0 -> 1.3.0 (MINOR, 2026-11-26)
Modified principles: XI: the standard tag vocabulary is data (`flows/tags.yaml`). The core handles tags as opaque strings and holds no tag name. The import-boundary test also forbids the standard tag names in core modules.
Modified sections: Technology and Security Constraints: (1) the `hop` rule: 3 or less for a free plan, 5 or less for a plan whose source is a verified template (spec 006). Every adapter recomputes the source from its own template files (same name, same hash of the parsed file, matching step shape). Else the source is `free`. (2) An exposed `exec` capability MUST have an `input_schema`. (3) A declared `exec` or `http` capability is `read` only. `http` uses `https`, except for `localhost` and `127.0.0.1`.
Added sections: none
Removed sections: none
Deferred TODOs: none. Pass 2 aligned specs 004 to 006 with 1.3.0 on 2026-11-26 (CLOSED). Pass 1 aligned the brief and specs 001 to 003 on the same day. The names that pass 2 adopted: `hop_limit`, `effective_source`, `validate_plan(plan, cards, starter, flows)`, `dialog_timeout`, and the transport and runtime changes of spec 003.
Migration: specs 001 to 003 and the design brief were updated on 2026-11-26 (1.3.0). Spec 001: `deny_rules` is a union with the default, `Transport.upload_file`, `pipe flows`, runtime status `waiting`. Spec 002: an exposed `exec` capability needs an `input_schema`. Spec 003: dialog step, context, plan proposal, `exclude_agents_of`, `on_fail`, `gate`, plan source, hop limit by source, new message types. Specs 004 to 006 adopted the `hop` rule of 1.3.0 in pass 2 (2026-11-26). Spec 006 relied on the variable `hop` limit as a documented deviation. It is now a rule of the constitution, and spec 006 has no Complexity Tracking row.
History: 1.0.0 (2026-11-25) first ratification: Core Principles (10), Technology and Security Constraints, Development Workflow, Governance; 1.0.1 (2026-11-25) PATCH: foreign-task tool rule allows a stricter empty tool set; 1.1.0 (2026-11-26) MINOR: principle XI; 1.1.1 (2026-11-26) PATCH: principle VIII wording; 1.2.0 (2026-11-26) MINOR: principle XI covers the transport; principle III covers declared capabilities; 1.3.0 (2026-11-26) MINOR: hop limit by plan source; tag vocabulary is data; exec input_schema; declared capabilities are read only
-->
# pipe.ai Constitution

## Core Principles

### I. No Server in the MVP
Slack is the UI, the message bus, and the task state. GitLab is the change gate and the scheduler. The MVP MUST NOT add a database, a web UI, or a hosted service.

Rationale: this is the fastest path to test the idea. The upgrade triggers are in the design brief.

### II. The Owner Controls the Agent
The adapter runs on the owner's laptop. Only the owner MUST decide who can send requests to the agent. Only the owner MUST decide which capabilities other people can use.

### III. Discovered Is Not Exposed
The adapter finds capabilities automatically. A capability that uses the owner's credentials MUST be `owner-only` until the owner exposes it. This includes a capability that the owner declares in the config file.

Rationale: this prevents the confused deputy problem.

### IV. Every Change Goes Through an MR
An agent MUST NOT push to `main`. The merge by a human is the approval.

### V. Thread Content Is Untrusted Input
The adapter MUST trust `metadata` only from bots that have an agent card. The adapter MUST trust approvals only from the thread starter or the agent owner.

### VI. Runtime-Agnostic Contract
The adapter MUST talk to the runtime through one contract. The first runtime is `claude -p`. The runtime MUST NOT know about `hop`, trust, or Slack. The adapter does all checks.

### VII. Business Rules Are Pure Functions (NON-NEGOTIABLE)
Router, trust, exposure, plan validation, and claim resolution MUST be pure functions. Each MUST have unit tests that run without Slack and without an LLM. Developers MUST write these tests first (TDD).

### VIII. Reuse Before Build
Review is a capability with the tag `review`. wiz-review is the first implementation. The adapter MUST copy the wiz-review patterns (tick, launcher, doctor).

### IX. Small Dependencies
The adapter uses Python, `slack_bolt`, and `pyyaml`. A plan MUST give a reason for each other dependency.

### X. STE for All Written Artifacts
Specs, plans, tasks, and docs MUST use Simplified Technical English: short sentences, one instruction per sentence, active voice, no idioms. Code, paths, and identifiers stay exactly as they are.

### XI. Core Is Capability-, Runtime-, and Transport-Agnostic
The core (routing, plan, steps, trust, claim, hop, timeout, catch-up) MUST NOT know plugins, skills, MCP, runtime tool names, wiz-review, GitLab, or Slack. The core MUST work only with `capability_id` values from agent cards. The core MUST handle tags as opaque strings. The standard tag vocabulary is data (`flows/tags.yaml`), not a core constant. Only a runtime adapter MAY turn capability IDs into runtime flags or runtime input. The core MUST talk to the chat system only through a `Transport` port. Only a transport adapter MAY import a chat library or read a chat field. A transport adapter MUST map its fields to the neutral identities `sender_id`, `sender_is_bot`, and `card_owner_id`. Trust rules stay in the core and use only these identities. Only a replaceable provider MAY read the state of an external system, such as an MR. Claude Code, Slack, wiz-review, and GitLab are first implementations, not core concepts. An import-boundary test MUST enforce this rule. It MUST forbid core imports of runtime and transport modules and core use of runtime tool types. It MUST also forbid the standard tag names as string constants in core modules, and it MUST cover every module in `src/pipe/core/`, also the modules that later specs add.

Rationale: one agent stack or one chat product must not shape the core. A new runtime, transport, review tool, or trigger needs no core change.

## Technology and Security Constraints

- Language and libraries: Python, `slack_bolt` (Socket Mode), `pyyaml`.
- Slack tokens MUST live in the macOS Keychain. A plain token MUST NOT appear in a config file. The same holds for the token of a declared `http` capability: the config holds a Keychain name only.
- Before the adapter posts text, it MUST remove strings that look like tokens.
- A task from a non-owner loads only exposed capabilities and gets no file tools. The core passes the capability IDs, the access level, and whether the requester is the owner. The runtime adapter sets the tool list. The task never gets `owner-only` tools.
- The adapter MUST limit each thread to `hop` 3 or less for a free plan. The limit is 5 or less for a plan whose effective source is a verified template. Every adapter MUST recompute the effective source from its own template files. A plan has the source `template:<name>@<hash>` only when the adapter has a template of that name, the hash of the parsed file is equal, and the plan steps match the template shape. In every other case the source is `free`. A plan source is untrusted text until an adapter has verified it. When the verification fails, the adapter MUST fail closed with the text "plan source not verified".
- An exposed `exec` capability MUST have an `input_schema`.
- A capability that the owner declares in config (`exec`, `http`) MUST have `access: read`. An `http` capability MUST use `https`, except for the hosts `localhost` and `127.0.0.1`.
- Agent cards MUST NOT contain MCP URLs, tokens, local paths, or config content.

## Development Workflow

- Every spec starts from the approved design brief in `docs/design-brief.md`. A spec MUST NOT add features that the brief lists as out of scope.
- Work follows the Spec Kit order: specify, plan, tasks, implement.
- Delegated work runs in a separate git worktree and branch.
- Each plan MUST include a check against this constitution.

## Governance

This constitution supersedes other practices in this project. An amendment MUST have a written reason, an approval by the project owner, and a migration note for affected specs.

Versioning follows semantic versioning. A MAJOR change removes or redefines a principle. A MINOR change adds a principle or section. A PATCH change fixes wording.

Each plan and each review MUST check compliance with this constitution. A deviation MUST have a written reason in the plan.

**Version**: 1.3.0 | **Ratified**: 2026-11-25 | **Last Amended**: 2026-11-26
