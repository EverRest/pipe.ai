# Research: Flow Catalog

All items are resolved. The decisions DQ1 to DQ12 are in "Design decisions" of [plan.md](plan.md). Source: `docs/design-brief.md` §3, §6, §8, §11, constitution v1.3.0, specs 001 to 005, and the owner decisions for 006 (all twelve confirmed on 2026-11-26). No Slack access and no network call was used.

## Checked in the repository (2026-11-26)

- This list is the state before pass 2. Pass 2 added to spec 003: `exclude_agents_of`, `source`, `gate`, `on_fail`, the dialog, the plan proposal, `effective_payload` over all results, and the functions `effective_source`, `hop_limit`, `claim_excluded`, `exclusion_deadlock`, `branch_target`, `next_step`. Spec 006 uses them and does not define them. The old bullets below stay as the history of the check.
- Spec 003 already has: tag steps (`agent: any`, `tag:<tag>`), `matches_tag`, `bind_step`, `payload` with `input_schema`, the claim rule, `no_claimer`, and `validate_plan(plan, cards, starter)`. A plan has at most 3 agent steps (`MAX_HOP = 3`, Q2). FR-021 forbids saved pipelines. FR-002 needs two named agents for a pipeline request.
- Spec 003 has no `exclude_agents_of`, no `source`, no `gate`, no `on_fail`, no dialog resume, no plan proposal, and no `Transport.upload_file`. The owner says some are being added now. [plan.md](plan.md) lists them in "Changes needed in 001 to 005". Pass 2 added all of them to spec 003 (see the first bullet above).
- Spec 005 has the trigger message with a fixed `pipeline`, `in_allowlist`, and the slow-capability rule. It passes the artifacts of the previous step only (`effective_payload`).
- Spec 004 has the owner gate for `write` steps. A template adds no bypass.
- The constitution (1.3.0) says `hop` 3 or less for a free plan and 5 or less for a verified template. This is a rule, not a deviation.
- Python, `slack_bolt`, and `pyyaml` are the project stack (constitution IX). No YAML loader is missing.

## Decisions

### D1. Template format is YAML (`yaml.safe_load`)
- Decision: templates are YAML files. The loader uses `yaml.safe_load` only.
- Rationale: the project already depends on `pyyaml` (the config file is YAML, constitution IX). YAML has comments, so a team can explain a template in the file. No new dependency. The owner and the team already read YAML in `config.yaml`.
- Alternatives: JSON (no comments, hard to review). TOML with `tomllib` from the standard library (no new dependency, but arrays of tables are heavy for steps, and it differs from the config format). See DQ2.
- Risk: YAML has odd types (`no` becomes false, numbers become int). The schema check rejects any value of a wrong type. `safe_load` blocks object construction.

### D2. The tag vocabulary is data, not core code
- Decision: `flows/tags.yaml` holds the vocabulary. The core gets it as an argument. The import-boundary test forbids tag names in core modules.
- Rationale: principle XI. The 005 boundary test already forbids the word `review` in the core. A constant list in `core/flows.py` would break it, and it would add capability knowledge to the core.
- Alternative: a constant in the core. Rejected for the reason above. See DQ3.

### D3. The hash is over the parsed data, not over the file bytes
- Decision: `flow_hash` = first 32 hex characters of SHA-256 of the canonical JSON of the parsed mapping.
- Rationale: line endings, comments, and quote style differ between machines and editors. The owner asked for "git sha or file hash". A git blob SHA needs git on the machine and changes with line-ending settings. The canonical hash needs only the file. Two machines with the same meaning get the same hash.
- Ceiling: 128 bits. A forged template needs a second preimage. This is not a practical attack. The control is the shape check, not only the hash.

### D4. Source check by recompute (DQ1 = b)
- Decision: every adapter recomputes the effective source from its own files. The plan `source` is a claim. The effective source is `template` only for a matching name, hash, and step shape.
- Rationale: a plan message comes from a bot that could be modified or stale. The `source` field is text. Only a check that the receiver does on its own data is a security control. The check is pure and stateless. It needs no new trust path and no new config. A stale copy fails closed to `free`.
- Alternatives: trust the claim from a trusted card (DQ1 a: any modified planner raises the limit). A hash allowlist in the owner config (DQ1 c: more config, and the owner must update it for each template change).
- Ceiling: the check cannot stop a team that merges a bad template. The review of `flows/` and the gates (✅, 004) are the controls.

### D5. Shape ignores goal, payload, and target
- Decision: the shape check compares agent kind, tag, access, `gate`, `on_fail`, `exclude_agents_of`, and count. It ignores `goal`, `payload`, and `target`.
- Rationale: the goal has the user text. A payload holds data for a capability. Neither one changes the risk class of a step (tag and access do). A human edit that changes only text keeps the template source (spec SC-005). A change of a tag or an access, an extra step, or a different order gives `free`.
- Cannot verify: whether a goal text can steer an agent to do more work. It can in any plan. The gates apply to every plan the same way.

### D6. No loops. One branch step.
- Decision: a template is a list. One step may have `on_fail: <last step id>`. The last step is the branch step. It is skipped on success. The flow ends after it.
- Rationale: owner decision 4. A branch to the last step needs no cycle check and no graph code. `next_step` is a few lines.
- Alternatives: a general `on_fail` to any later step (more rules, no need in the catalog). A retry loop (rejected by the owner).

### D7. Branch only on `run_failed`
- Decision: only a failure that the capability reports (`reason: run_failed`) branches. A timeout, `no_claimer`, `invalid_payload`, `invalid_result`, `rejected`, a hop refusal, and `owner offline` do not. See DQ5.
- Rationale: troubleshoot is useful when the check itself shows a fault. A timeout or a missing claimer is an infrastructure problem. It needs a "Retry" button. A branch would hide it.

### D8. The mid-flow ✅ reuses the status `needs_approval`
- Decision: a step with `gate: approval` ends with a type 5 message with `status: needs_approval`. ✅ gives a second type 5 with `done` and `next`. A step that returns a proposal does the same (owner model).
- Rationale: it reuses the status, the ✅ rule of spec 003, and the duplicate-handoff rule of spec 005. No new message type. See DQ6.
- Alternative: allow an `approve` step in the middle (change the 003 rule 4). Rejected: a human step is a button with no agent, and it has no result to show.

### D9. `exclude_agents_of` is a claim rule plus a plan check
- Decision: at run time, `claim_excluded` ignores a claim from an agent that holds the winning claim of an excluded step. At plan time, `exclusion_deadlock` reports only a certain deadlock (one agent offers both tags).
- Rationale: at plan time the claimant of a tag step is not known. A full check is not possible. A certain-deadlock check catches the common setup error (a team with one agent). The run-time rule is exact. `no_claimer` covers the rest.
- Cannot verify: a team of two agents where both can claim `implement`. The first claimant of `implement` is excluded from `review`. The other agent can review. This is the goal.

### D10. `$agent` and `$starter` are the only agent placeholders
- Decision: `$agent` is the second named agent. `$starter` is the thread starter (for the final human step).
- Rationale: `delegate` must name the other owner's agent. The name comes from the person, not from the file. A template with a concrete agent would break owner decision 1.
- Alternative: a parameter `agent=<name>`. A mention is clearer in chat and gives the card without a lookup by name. See DQ9.
- The `$agent` step binds the lowest capability ID of that card with the tag. This is the rule of `bind_step` of spec 003 (lowest ID). The core stays free of tool names.

### D11. Parameters only for the tag and the goal text
- Decision: `params` can fill `tag:$<param>` and `{<param>}` in a goal. Each value must be in a fixed list. One flow (`nightly`) needs them.
- Rationale: `nightly` runs `e2e` or `deps-check`. Two files would double the catalog. A free value would be an injection point. A fixed list is safe.

### D12. `pipe flows` shows the hash
- Decision: `pipe flows` is read-only. It shows origin, hash, needed tags, and missing tags.
- Rationale: when a hop is refused for an unverified source, the owner must see which copy differs. The hash in the list is the fastest check.

### D13. Dialog and proposal are spec 003 features
- Decision: 006 does not implement the dialog resume or the plan proposal. Flows use them. The dialog rules are spec 003 code (T094 to T099). The flow tests use the `FakeRuntime` that returns `needs_input`.
- Rationale: the owner adds them to the base specs. Two implementations of one rule would conflict.
- Cannot verify: the exact message shape of the dialog. Tasks T046 and T048 use the shape of the base spec when it exists.

### D14. The loader is outside the core
- Decision: `src/pipe/flows_io.py` reads the files and the YAML. `core/flows.py` gets plain mappings.
- Rationale: principle VII (pure functions) and XI (the core does no I/O, so a test needs no disk). The loader has its own tests with `tmp_path`.
- Ceiling: the files are read at each plan and at each handoff check. The catalog has about 11 small files. A cache with a modification time is the upgrade if the read time shows in a test.

### D15. Free plans keep limit 3, and can use the new step fields
- Decision: `exclude_agents_of`, `gate`, and `on_fail` are plan-step fields. They are valid in a free plan, with the same structure rules. Only the limit depends on the source.
- Rationale: one `validate_plan`. No second rule set. The fields can only add a stop or a restriction. A free plan with `on_fail` still has at most 3 agent steps.
