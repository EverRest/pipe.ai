# Implementation Plan: Pipelines from Chat

**Branch**: `003-chat-pipelines` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-chat-pipelines/spec.md`

## Summary

A person writes one message in `#pipe-work` that names two or more agents. The first named agent is the planner. Its adapter reads the agent cards from `#pipe-agents`, runs the runtime with no tools and a plan schema to get a plan, and checks the plan in code (`validate_plan`). A plan step is `{agent, capability, access, goal}` with an optional `payload` and the optional `exclude_agents_of`, `gate`, and `on_fail`. A plan has the optional `source`. The `capability` is a `capability_id` from the card, or `tag:<tag>` when the `agent` is `any` (late binding: any agent with a fitting exposed capability can claim the step). The `access` is `read` or `approve` (`write` comes in spec 004). The adapter posts the plan in the thread as a `pipe.task.v1` message with `status: needs_approval`, or it posts the errors. The thread starter (or the planner owner) adds ✅. The planner then posts a handoff message to the agent of step 1. The handoff mentions the agent with `Transport.mention(bot_user_id)` (the handle comes from its card). A tag step mentions every eligible agent. That adapter claims the step, resolves duplicate claims by the lowest `ts` (`resolve_claim`), runs the step, and posts a result message that names the next agent. The last step can be a human approval with a button. The thread is the state. There is no database and no coordinator. The decision logic is in pure functions: `route`, `validate_plan`, `resolve_claim`, and `build_run_request`.

The pipeline core knows only `capability_id` values. It gives the runtime a `RunRequest{capabilities, access, requester_is_owner, output_schema?}`. A pure function picks the runtime adapter by the `runtime` of the capability (`claude`, `exec`, or `http`). Only the runtime adapter maps a `RunRequest` to its own flags or input. The `claude` adapter maps it to `--plugin-dir`, `--allowedTools`, `--mcp-config`, `--tools`, and the deny rules. The `exec` and `http` adapters run the capabilities that the owner declared (spec 002). Before a run, the core checks the step `payload` against the `input_schema`. After it, the core checks `data` against the `output_schema`. The adapter reuses the 001 `Transport` port, dedupe, in-flight set, catch-up, `claude -p` wrapper, `scrub`, and config. dedupe, in-flight set, catch-up, `claude -p` wrapper, `scrub`, and config. It reuses the 002 card format, the capability classes, and the load-set builder (inside the `claude` adapter). A new script, `pipe metrics`, reads `#pipe-work` and the MR state from a replaceable provider (GitLab is the first one) and prints the experiment metrics. Details: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.15 (same as 001 and 002).

**Primary Dependencies**: `slack_bolt`, `pyyaml` (from 001). Test-only: `pytest`. No new dependency (research.md D14). The GitLab read in `pipe metrics` and the `http` runtime adapter use `urllib` from the standard library. The schema validator is `core/schema.py` of spec 002 (no `jsonschema` package).

**Storage**: No new file under `~/.pipe/`. The thread messages hold the pipeline state. The adapter keeps three things in memory only: the card cache, the map from `bot_user_id` to `bot_id` (made from the cards), and the step timers. 001 files (`state.json`, `seen.json`) are unchanged. `~/.pipe/run/<run_id>/` (from 002) holds the load files during one step run. Only the `claude` adapter makes and removes it.

**Testing**: `pytest`. Pure functions have unit tests first, with no Slack and no LLM (SC-008): `route`, `validate_plan`, `resolve_claim`, `trusted_cards`, `check_task_msg`, `build_run_request`, `map_request` (`claude` adapter), `thread_status`, `step_status`, `render_task`, `compute_metrics`, and (second batch) `effective_source`, `hop_limit`, `claim_excluded`, `exclusion_deadlock`, `branch_target`, `next_step`, `gate_pending`, `open_question`, `dialog_expired`, `flow_word`, `effective_payload`. An import-boundary test (`test_core_boundary.py`) proves that the core imports no runtime-specific module (SC-011). Slack, the runtime, and the MR-state provider sit behind ports with fakes (`FakeTransport` and `FakeRuntime` from 001 and 002, new `FakeMrState`). Integration tests run the adapter with fakes through the full flow: plan, ✅, steps, approve button, hop refusal, claim race, timeout, retry, offline wait, catch-up. One stub-`claude` test checks the new command flags. A manual run with real Slack and real `claude` is in [quickstart.md](quickstart.md).

**Target Platform**: macOS laptop (same as 001). `pipe metrics` runs on any team member laptop.

**Project Type**: Extension of the 001 and 002 CLI and background process (`pipe run`, new `pipe metrics`).

**Performance Goals**: A hung step shows `failed` and a "Retry" button less than one minute after the step time limit (SC-006). A plan appears in the thread without other tools to follow it (SC-007).

**Constraints**: No server, no database, no web UI. One runtime call at a time per adapter (001). The `claude` adapter keeps `--restricted` on every run. A step run loads only exposed capabilities. No plain token in any file. A free plan has at most 3 agent steps and a verified template at most 5 (`hop` limit by plan source, decision Q2 as changed by N7). The core names no plugin, skill, MCP server, runtime tool, wiz-review, or GitLab (principle XI).

**Scale/Scope**: 3 to 6 developers. A few pipelines per day. Each pipeline has 2 to 4 steps.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.3.0.

| Principle | Pre-research | Post-design | Note |
|---|---|---|---|
| I. No Server in the MVP | PASS | PASS | Thread messages are the state. Timers and caches are in memory. `pipe metrics` reads Slack and the MR provider. No database, no service. |
| II. The Owner Controls the Agent | PASS (Q6) | PASS (Q6) | A step runs only with exposed capabilities. The owner decides exposure (002). The file access comes only from the `claude` adapter config (`runtime.claude.owner_tools`, `runtime.claude.repo_roots`). 003 has no owner gate for a step that another person started (decision Q6): exposure is the limit. The allowlist and the accept/reject button belong to spec 004. The owner should set `max_budget_usd`, because another person's step spends the budget of the owner. |
| III. Discovered Is Not Exposed | PASS | PASS | `validate_plan` rejects a step whose `capability` is not in the card of its agent (the card lists exposed capabilities only). The `claude` adapter loads exposed items only, checks exposure again at run time, and blocks `owner-only` items. |
| IV. Every Change Goes Through an MR | PASS | PASS | The adapter adds no push. The `claude` adapter always denies `Bash(git push:*)` (`deny_rules`). `access: read` removes the write tools. `access: write` is refused in 003. Residual risk: an owner who widens `runtime.claude.owner_tools`. See Q5. |
| V. Thread Content Is Untrusted Input | PASS | PASS | `trusted_cards` and `check_task_msg` ignore metadata from a bot without a card. They also ignore a message whose `by` differs from its author. ✅ and button clicks count only from the thread starter or the agent owner. The plan comes only from the planner (first named agent). The thread goes to the runtime as untrusted text (001 D7). |
| VI. Runtime-Agnostic Contract | PASS | PASS | `RuntimeInput` gets one new field, `request` (`RunRequest`). The 001 chat path is unchanged. The runtime gets `task.id`, `task.step`, the step goal, and `request`. It gets no `hop`, trust, or Slack data. The planner schema is a flag of the `claude` adapter. See [contracts/runtime-request.md](contracts/runtime-request.md). |
| VII. Business Rules Are Pure Functions | PASS | PASS | `route`, `validate_plan`, `resolve_claim`, trust checks, `build_run_request`, `map_request`, `thread_status`, and `compute_metrics` are pure. Test tasks come before implementation tasks. |
| VIII. Reuse Before Build | PASS | PASS | Reuses 001 (app, dedupe, in-flight, catch-up, runtime wrapper, `scrub`, `escape_mentions`, config, fakes) and 002 (card format, the core `state_of`, the `claude` adapter `classify`, the load-set builder, `prepare`, `cleanup`). A review step is a normal step whose capability has the tag `review`. wiz-review is the first implementation behind a card (spec 005). |
| IX. Small Dependencies | PASS | PASS | No new dependency. |
| X. STE for All Written Artifacts | PASS | PASS | All artifacts use STE. |
| XI. Core Is Capability-, Runtime-, and Transport-Agnostic | PASS | PASS | The core trust and claim rules use the neutral identities of 001 (`sender_id`, `sender_is_bot`, `sender_handle`, `card_owner_id`) and import no `transport_slack*` module. The adapter is picked by a pure function and the adapters `runtime_exec`, `runtime_http`, and `runtime_claude` sit outside `core/`. The core modules (`pipeline`, `trust`, `claim`, `route`, `runrequest`, `render`, `metrics`, `source`, and the 002 modules `capability`, `exposure`, `card`, `summary`) use `capability_id` values only. `build_run_request` gives `RunRequest{capabilities, access, requester_is_owner}`. Only `runtime_claude_request.py` and `runtime_claude.py` turn it into flags. The MR state comes through `MrStatePort`. `gitlab_io.py` is the first provider. `test_core_boundary.py` enforces the rule. |

Technology and Security Constraints: tokens in Keychain (PASS: the GitLab token for `pipe metrics` is a `keychain:` reference in the provider config). Scrub before post (PASS: every posted text and every `reason` passes `scrub` and `escape_mentions`). A foreign-started step loads exposed capabilities only and gets no file tool (PASS: `build_run_request`, `map_request`, tests T032, T072). `hop` 3 or less for a free plan, 5 or less for a verified template (PASS: `hop_limit(effective_source)` in `route` and `validate_plan`; every adapter recomputes the source from its own template files; an unverified source fails closed with "plan source not verified"; tests T090 to T093). An exposed `exec` capability has an `input_schema` and declared capabilities are `read` only (PASS: spec 002 config checks; the `exec` adapter runs only exposed capabilities). Cards hold no MCP URL, token, or path (PASS: 003 does not change the card; it only reads it).

**Result**: PASS. No deviation. No Complexity Tracking row. The eight design questions are decided (below). Q6 touches principle II: the owner confirmed it.

## Design decisions

The owner of the project decided the eight design questions of the first plan. Each decision is in force. The tasks follow them.

- **Q1 = (a). Pipeline request.** A message is a pipeline request when it names 2 or more distinct agents that have a card. A message with one agent is a normal chat (001). Amended by N9: a `flow:<name>` word with one agent is also a pipeline request. Affected tasks: T017, T022, T110.
- **Q2 = (a). Hop count.** Every handoff counts for `hop`, including the first handoff from the planner. A free plan has at most 3 agent steps. `validate_plan` rejects a longer plan. Amended by N7: a verified template has at most 5. The human approval step adds no hop. FR-010 follows from `hop` 3 (research.md D6). Affected tasks: T016, T028, T030.
- **Q3 = (a). Who may click approve.** Only the thread starter or the owner of the agent that posted the button may click. `validate_plan` rejects any other human step. Affected tasks: T016, T034, T042.
- **Q4 = (a). Adapter that is down.** Only the owning adapter acts. At start and at reconnect, it fails its own stale `running` steps with `reason: interrupted` and a "Retry" button. While the adapter is down, the step stays `running`. Affected tasks: T048, T052, T056.
- **Q5 = (a). What a step can use.** An owner-started step (`requester_is_owner` true) gets the owner tools of the runtime adapter plus the loaded exposed capability. For the `claude` adapter these are `runtime.claude.owner_tools` (default `Read`, `Grep`, `Glob`), cut to the tools that match the access level (`read`: no file writes). A step that another person started gets the exposed capability only and no file tools. No `owner-only` item loads in any step. Affected tasks: T032, T036, T072, T073.
- **Q6 = (a). No owner gate in 003.** Exposure is the limit. The allowlist and the accept/reject button come in spec 004. Note: the owner should set `max_budget_usd`, because another person's step spends the budget of the owner. Affected tasks: T036, T040.
- **Q7 = (b). Mention of the next agent.** The card holds `bot_user_id` (spec 002). The adapter gets it from `auth.test` when it publishes the card. The next agent is mentioned as `<@bot_user_id>`. 003 does not add the `users:read` scope. The `bots.info` and `users.info` path is removed. Affected tasks: T009, T013, T014, T015. A trust check on the card (message `user` equals `bot_user_id`) is in research.md D3 and D5.
- **Q8 = (a). "Finished without manual help".** The pipeline ends `done`, no step was `failed`, and no human message appears after the start message, except the approval clicks. A `waiting` step is not manual help. Affected tasks: T058, T061.

Design choices that follow from the capability-agnostic rule (principle XI) are in research.md D19 to D21: the field `phase`, the field `access`, the `runtime` config section, and the `RunRequest` extension of the 001 contract. The owner confirmed them on 2026-11-26.

The owner also confirmed these decisions on 2026-11-26:

- **Card trust (Q7).** `trusted_cards` keeps both checks: the card message `user` must equal `bot_user_id` when it is present (assumption A8), and the card with the lower `ts` keeps a duplicate `bot_user_id`. Test task: T007.
- **Planner request.** The planner always runs as `RunRequest((), "read", False)`, with no file tool, also for the owner. Test tasks: T020, T032.
- **Step request.** A step loads only its own capability. Test tasks: T032, T072.

- **Late binding and runtime selection (2026-11-26, owner decision).**
  - **LB1. Access fit.** A step `access` fits a card capability when the card entry has no `access`, or when both are equal. A `read` step does not fit a declared `write` capability. Affected tasks: T084, T085.
  - **LB2. Tag step claim.** The handoff mentions every eligible agent. The lowest claim `ts` wins (as before). The winner is the only agent that posts later messages for the step. For a `write` step, the 004 gate runs for the winner. Affected tasks: T086, T087.
  - **LB3. Nobody claims.** After `step_timeout_min`, the sender of the handoff posts `failed`, `reason: no_claimer`, with a "Retry" button. "Retry" posts the handoff again (same `hop`). There is no `waiting` message for a tag step. Affected tasks: T088, T089.
  - **LB4. Runtime selection.** The core picks the adapter by `Capability.runtime`. Declared capabilities run in `runtime_exec` or `runtime_http`. The adapter checks exposure again at run time. Affected tasks: T074 to T081.
  - **LB5. Schemas.** The core validates `payload` against `input_schema` after the claim and before the gate. It validates `data` against `output_schema` after the run. Affected tasks: T082, T083.

## Design decisions, second batch (2026-11-26, constitution 1.3.0)

The owner confirmed these decisions on 2026-11-26. The numbers N1 to N13 are local to this spec. Spec 006 uses the names DQ1 to DQ12 for the same points. Each decision has an FR, a data-model rule, a contract text, and a test-first task pair (principle VII).

- **N1. Dialog step (006 DQ7 = a).** A step returns `waiting` with `reason: needs_input`. Only the thread starter or the agent owner answers. The answer mentions the agent. The SAME step runs again on the SAME agent. `hop` does not grow. The step timer counts only runs. `dialog_timeout_h` (default 24). After it: `failed`, `dialog_timeout`, "Retry". FR-036, SC-018, US9. Contract: task-metadata type 10, runtime-request. Tasks: T094 to T099 (pairs T094/T095, T096/T097, T098/T099), T112, T113.
- **N2. Context.** `effective_payload` gives the `text` and `artifacts` of ALL previous steps. Large context goes by link. `check_input` validates the effective payload. FR-037, SC-019. Tasks: T100, T101.
- **N3. Plan proposal and gate (006 DQ6 = a, DQ12 = a).** A step returns `proposal`. It passes `validate_plan` and gets `needs_approval`. A new ✅ releases. A step never starts work by itself. In a template flow an approved proposal is context only. FR-038, FR-043, SC-020, US10. Tasks: T102 to T105.
- **N4. `exclude_agents_of`.** Optional step field. The claim rule ignores a claim from an agent that holds an excluded step. The planner sets it for review steps. This replaces the general rule of spec 005 DQ8. FR-039, SC-021, US11. Tasks: T106, T107.
- **N5. `on_fail` (006 DQ5 = a).** One branch per plan, no loop, only on `run_failed`. A timeout uses "Retry". A `failed` message can carry `next` (type 11). FR-040, SC-022, US11. Tasks: T108, T109.
- **N6. Free plans (006 DQ11 = a).** A free plan may use `gate`, `on_fail`, and `exclude_agents_of`. The limit stays 3. FR-041. Tests: T102, T106, T108.
- **N7. Plan source and hop limit (006 DQ1 = b, DQ10 = a).** `pipeline.source`. `validate_plan(plan, cards, starter, flows)` and `route` recompute it. A mismatch or an edit gives `free`. Two copies that differ fail closed with "plan source not verified". `MAX_HOP_FREE = 3`, `MAX_HOP_TEMPLATE = 5`. `ThreadState.flows`. FR-042, SC-023, US12. Tasks: T090 to T093.
- **N8. FR-021 relaxed.** Templates from git (`flows/`) and owner overrides (`~/.pipe/flows/`) are allowed. Saving pipelines from chat stays forbidden. FR-021, SC-024. Test: T110.
- **N9. FR-002 relaxed.** A `flow:<name>` word makes a pipeline request, also with one named agent. FR-002, FR-044, SC-024. Tasks: T110, T111.
- **N10. Planner `flow` (006 DQ4 = a).** The planner output may be a template name. The core expands. FR-044, SC-024. Tasks: T110, T111.
- **N11. Task metadata.** Type 5 gets `needs_approval` and a ✅ release. New types 10 and 11. New actions `plan_flow`, `release`, `resume`, `expire_dialog`. Each type has a trust check. FR-045. Tasks: T112, T113.
- **N12. Access fit.** A step access fits a capability only on exact equality, or when the card entry has no `access`. Confirmed. FR-029. Tests: T084 (existing).
- **N13. Rejected `write` tag step.** It ends `failed`, `rejected`, with no second claimer. Deferred. FR-046, SC-026. Tasks: T114, T115.
- **Boundary test.** T071 covers every module in `src/pipe/core/` (glob), the new `source.py`, the modules of specs 005 and 006, and the standard tag names. SC-025. Task: T071 (changed).

### Defaults applied by the spec author, open for the owner (see the report of this pass)

- **U2. A proposal in a free plan** is context only, like in a template (not "replaces the remaining steps"). Reason: no new execution path. 006 FR-028 allows an option (b) for free plans. Not applied.
- **U3. A dialog answer must mention the agent.** The adapter reads mentions only (no `message.channels` scope). Alternative: subscribe to `message.channels`.
- **U4. `check_input` validates the effective payload** (with `context` and `artifacts`). A schema with `additionalProperties: false` must list both keys. Alternative: validate the plan `payload` only.
- **U5. The reason for a dialog wait that expires is `dialog_timeout`** (owner text of this pass). Spec 006 FR-027 says `timeout`. Spec 006 must follow.
- **U6. A dialog answer is not "manual help"** in the metric `clean_pipelines_share`.
- **U7. `run_failed` is the runtime `status: failed` only.** A `RuntimeFailed` (exit code, http code) does not branch.

## Project Structure

### Documentation (this feature)

```text
specs/003-chat-pipelines/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── task-metadata.md
│   ├── plan-schema.md
│   ├── runtime-request.md
│   └── cli.md
├── checklists/requirements.md
└── tasks.md             # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

New files are marked `+`. Changed 001 or 002 files are marked `~`.

```text
src/pipe/
├── core/                            # PURE functions only. Pipeline core: no runtime-specific module
│   ├── pipeline.py          +       # types; ts_key; parse_task; find_plan; validate_plan(plan, cards, starter, flows); step_status; thread_status; next_hop; access_fits; matches_tag; bind_step; step_agent; exclusion_deadlock; branch_target; next_step; gate_pending; open_question; dialog_expired
│   ├── source.py            +       # effective_source(plan, flows, cards, starter); hop_limit(source); MAX_HOP_FREE; MAX_HOP_TEMPLATE; parse_source
│   ├── trust.py             +       # trusted_cards(messages); check_task_msg(msg, cards)
│   ├── claim.py             +       # resolve_claim(claims) -> winner; claim_excluded(plan, thread, i, agent_id)
│   ├── route.py             +       # route(event, thread_state) -> Decision; first_agent; mentions (tag steps: eligible agents claim); flow_word; actions plan_flow, resume, release, expire_dialog
│   ├── runrequest.py        +       # RunRequest (with output_schema); build_run_request(step, starter, owner, output_schema=None) -> RunRequest; pick_runtime(caps, capability_id, default) -> str; check_input(step, cap); check_output(output, cap); effective_payload(step_payload, results)
│   ├── render.py            +       # render_task, render_plan, render_errors (text of each message; uses scrub, escape_mentions)
│   └── metrics.py           +       # compute_metrics(threads, mr_states, now) -> Metrics; render_metrics
├── cards.py                 +       # CardCache: reads #pipe-agents, keeps trusted cards in memory (TTL 5 min, refresh on unknown bot); agent_users() from card bot_user_id
├── planner.py               +       # run_planner: prompt, runtime call with plan schema, validate, post
├── stepper.py               +       # claim flow, run step (RuntimePort.run with RunRequest), finish, approve, retry, interrupted, offline timer
├── runtime_claude_request.py +      # `claude` adapter, pure: map_request(request, caps, exposed, claude_cfg) -> StepTools(policy, load)
├── runtime_exec.py          +       # `exec` runtime adapter: RuntimePort over a local command (argv list, no shell, minimal env, timeout)
├── runtime_http.py          +       # `http` runtime adapter: RuntimePort over a POST (urllib, Keychain token by name, no redirect)
├── runtime_select.py        +       # RuntimePort that delegates to the adapter that pick_runtime names
├── gitlab_io.py             +       # first MrStatePort provider over urllib: MR state by URL (host must equal the configured GitLab host)
├── metrics_cli.py           +       # gather threads and MR states, call compute_metrics, print
├── config.py                ~       # work_channel; runtime section (name, claude: owner_tools, repo_roots, deny_rules); mr_state section (provider, gitlab: url, token)
├── ports.py                 ~       # Transport: replies, delete_message; buttons on post and update; RuntimeInput.request; MrStatePort
├── transport_slack.py              ~       # the new Transport methods
├── runtime_claude.py        ~       # build_cmd(..., schema=None); run(inp): map_request, prepare, build_cmd, cleanup; Read/Grep/Glob path rules only when in tools
├── adapter.py               ~       # reaction_added and button handlers; route dispatch; catch-up through route; wake at start and reconnect
└── cli.py                   ~       # `pipe metrics`

tests/
├── unit/                            # test_pipeline.py, test_validate_plan.py, test_trust.py, test_claim.py, test_route_*.py,
│                                    # test_hop_rule.py, test_thread_status.py, test_runrequest.py, test_runtime_claude_request.py,
│                                    # test_render.py, test_metrics.py, test_cards.py, test_gitlab_io.py, test_core_purity.py,
│                                    # test_core_boundary.py
│                                    # (+ changes to test_config.py, test_runtime_claude.py, test_catchup.py)
├── fakes.py                 ~       # FakeTransport: replies with metadata, reactions, delete, buttons; FakeMrState; make_thread builder
├── integration/                     # test_plan_flow.py, test_run_steps.py, test_trust_hop.py, test_claims.py,
│                                    # test_timeout_retry.py, test_catchup_pipeline.py, test_metrics_cli.py
└── manual/                          # none new
```

**Structure Decision**: Single project, same layout as 001 and 002. All pipeline rules sit in `core/` as pure functions. All Slack, runtime, MR-state, and timer code sits outside `core/` and behind a port. All Claude Code specifics sit in the `claude` adapter files: `runtime_claude.py`, `runtime_claude_request.py` (003), and `runtime_claude_loadset.py` and `runtime_claude_load.py` (002).

## Complexity Tracking

No constitution deviation. No row.
