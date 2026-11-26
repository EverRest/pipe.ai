# Research: Pipelines from Chat

All "NEEDS CLARIFICATION" items of the Technical Context are resolved. The eight design questions are decided in "Design decisions" of [plan.md](plan.md). Source of decisions: `docs/design-brief.md` §5.2, §6 to §10. This file does not change them. No Slack access and no network call was used for this research.

## Checked in the repository (2026-11-26)

- 001 has no card cache. 002 reads only its own card (`pick_own_card`). Spec 003 adds the card cache (D3).
- 002 `load_set(caps, exposed, capability_ids)` is pure and belongs to the `claude` adapter. It takes capability IDs (002 D16). So the core needs no filter step (D9).
- 001 `build_cmd` adds path allow rules for `Read`, `Grep`, and `Glob` when the tool list holds them. A step with no file tool gets no path rule (D9).
- 001 `RuntimeInput.task` has the keys `id`, `purpose`, `from_agent`, `owner`, `hop`, `pipeline`, `step`. 001 `RuntimeInput.tools` is built by `tools_for` from `runtime.claude.owner_tools`. 003 adds `RuntimeInput.request` (D19). 003 uses `task.id`, `task.purpose` (`plan` or `step`: the label of the call), `task.step`, and `task.pipeline` (D8).
- The card has `bot_id`, `bot_user_id`, and `owner` (spec 002 FR-021). A mention needs no extra Slack call (D5).

## Decisions

### D1. Thread state model
- Decision: the state of a pipeline is the list of `pipe.task.v1` messages in the thread. The adapter builds `ThreadState` from `conversations.replies` with `include_all_metadata`, the card cache, and the 001 seen set. Every Slack event is only a trigger. The adapter re-reads the thread and then calls `route`.
- Rationale: the brief says no coordinator and no database (principle I). A re-read after each event gives the same result for a live event and for a catch-up.
- Alternatives: keep a local state file per pipeline. Rejected: a second copy of the state can differ from the thread, and a restart or a second laptop would not see it.

### D2. Message types and in-place updates
- Decision: [contracts/task-metadata.md](contracts/task-metadata.md) lists eight message types: plan, rejected plan, start handoff, step claim, step result (handoff or final), approval request, waiting, hop refusal. A step claim message is posted once and updated in place with `chat.update` (`claimed`, `running`, `done`, `failed`). A handoff to the next agent is always a new message, because an edit sends no `app_mention` event.
- Rationale: in-place updates keep the thread quiet (metric "noisy messages" < 10%). New messages carry the mention that wakes the next adapter.
- The status of a step is the status of the latest trusted message that has the same `step` and the `phase` `step`. The plan-phase messages are not step messages.
- Alternatives: append-only messages for each state change. Rejected: more noise in the thread.

### D3. Card cache and trust (principle V)
- Decision: `CardCache` reads `#pipe-agents` with `history` (002 port). The pure function `trusted_cards(messages)` keeps a card only when the message has `sender_is_bot` true, the `event_type` is `pipe.card.v1`, the `sender_id` of the message equals `payload.bot_id` (002 contract rule 6), the message `sender_handle` (when present) equals `payload.bot_user_id`, and the 002 function `validate_card` returns no violation. If two cards claim the same `bot_user_id`, the card with the lower message `ts` keeps it and the other card is dropped. Both checks are a confirmed owner decision (2026-11-26). This stops a bot with a card from taking the mention of another agent (the card `bot_user_id` is the only source of mentions, D5). The cache lives in memory. It refreshes at start, after 5 minutes, and once (at most one refresh per 60 seconds) when a message comes from an unknown `sender_id`. If the bot still has no card, the message is ignored.
- Rationale: 002 says that 003 owns the trust in other cards. A forged card needs a bot user in the workspace, and a bot cannot post as another bot.
- Alternatives: pins list only. Rejected: a pin needs `pins:read` and the card may be unpinned. History is the source of truth.

### D4. Trust check of a task message (`check_task_msg`)
- Decision: a message is a valid task message only if all of the following are true. (1) The author is a bot with a card. (2) `event_type` is `pipe.task.v1`. (3) The payload has `v` 1, a known `phase`, a known `status`, an integer `hop`, an `access` (when the phase is `step`) in the known set, and `task_id` equal to the thread `ts`. (4) `by` equals the `sender_id` of the author. (5) For the plan: `by` equals the planner (the first agent named in the parent message). (6) For a step claim: `by` equals the agent that the plan assigns to the step (for a tag step: an agent whose card is eligible). (7) For any other step message of a tag step: `by` equals the winner of the claims (`step_agent`). (8) A type 10, type 11, or type 5 `needs_approval` message follows the checks of contracts/task-metadata.md rule 7 (D31). (9) A claim from an agent that holds an excluded step is ignored (`excluded`, D29). Any other message is ignored with a reason (`no_card`, `bad_payload`, `by_mismatch`, `not_planner`, `not_assigned`, `excluded`, `bad_branch`, `already_branched`). The ignore reason is logged and is never posted.
- Rationale: FR-008. Checks (4) to (6) stop a bot with a card from acting as another bot or from taking a step that the plan gave to another agent. Check (6) is stricter than the brief ("two agents take one step"); in practice two adapters of the same bot cause a double claim (D7).

### D5. Mention of the next agent (Q7 = b)
- Decision: a handoff message holds `<@bot_user_id>` of the next agent in its text. `bot_user_id` comes from the card of that agent (spec 002 FR-021). The adapter calls no `bots.info` and no `users.info`. 003 adds no `users:read` scope. `CardCache.agent_users()` builds the map from `bot_user_id` to `bot_id` from the trusted cards. The map is in memory. The same map gives the planner check: the first `<@U>` in the parent text that maps to a card is the planner.
- Rationale: the existing `app_mention` path (001) wakes the next adapter and the 001 catch-up finds the handoff after downtime. No new event subscription for handoffs. No new scope.
- Trust (confirmed by the owner, 2026-11-26): a card with a wrong `bot_user_id` could take the mention of another agent. D3 gives two checks, and both stay: the message `sender_handle` must equal `bot_user_id` when it is present (assumption A8), and the card with the lower `ts` keeps a duplicate `bot_user_id`. Test task: T007.
- Contingency (not chosen now): subscribe to `message.channels` and match `next.agent == self`. Kept as the fallback if A1 fails (see "Cannot verify").

### D6. Hop rule (Q2 = a)
- Decision: `hop` of a message is the number of agent handoffs up to and including the handoff that the message makes. The plan message has `hop` 0. The start handoff has `hop` 1. Each result message with `next` has the `hop` of the claim plus 1. The approval request has the `hop` of the claim. A receiving adapter refuses a handoff with `hop` greater than `hop_limit(effective_source)`: 3 for a free plan, 5 for a verified template (D25). It posts one `failed` message with `reason: hop limit exceeded` (plus ` (plan source not verified)` when a declared template is not verified) and runs nothing. `validate_plan` rejects a plan with more agent steps than that limit, so an honest pipeline never reaches a `hop` above it.
- FR-010: with the limit 3 (a free plan), a step that passes back and forth between two agents at most two times is implied. The longest back-and-forth chain is A to B (hop 1), B to A (hop 2), A to B (hop 3). A fourth handoff is refused. A test documents this (T028).
- Alternatives: the first handoff does not count (4 agent steps); `hop` counts only returns to an agent. Both were rejected by decision Q2 = a.

### D7. Claims
- Decision: the adapter that gets a valid handoff posts a claim message at receipt (before it queues the work). It waits 2 seconds (constant `CLAIM_SETTLE_S`), reads the thread again, and calls `resolve_claim` on the claims of this step (same `step`, assigned agent, status other than `failed`, posted after the handoff). The winner is the claim with the lowest `ts` (compared as numbers). If two claims have the same `ts`, the lower `by` string wins. If the adapter lost, it deletes its own claim message (`chat.delete`) and runs nothing. Identity is the `ts` of the claim, not `by`, because two adapters of one bot share `by`.
- A claim message that has status `failed` does not count. So a "Retry" click starts a new claim that can win.
- Ceiling: a claim with a lower `ts` that becomes visible after the 2 second wait causes a double run. This needs a Slack delay of more than 2 seconds. Accepted for the MVP. The adapter checks the claims once more before it posts the result, and drops the result if it is not the winner (cheap, one read).
- Rationale: FR-014, SC-005. A claim at receipt (not at dequeue) shows `claimed` while the step waits in the queue. So a busy adapter does not look offline (D10).

### D8. Step run
- Decision: for a `read` step, the stepper (1) updates the claim message to `running`, (2) calls the pure `build_run_request(step, starter, owner)` (D9), (3) calls `RuntimePort.run` with `task = {id: thread_ts, purpose: "step", step: i, pipeline: {goal}}`, the thread messages as untrusted text, and `request` (the `RunRequest`). The runtime adapter maps the request to its own flags, makes its load files, runs, and removes the files in a `finally` (D9). The runtime timeout is `step_timeout_min` (001). Only the runtime status `done` continues the pipeline. Since the second batch: `waiting` with `needs_input` starts the dialog (D26), `done` with a `proposal` or a `gate` waits for ✅ (D28), and `failed` gives `reason: run_failed` and the branch rule (D30). Any other status (`needs_approval`, `delegate`) ends the step as `failed` with a fixed reason (`runtime status <s>`). The goal and the capability come from the plan in the thread (trusted source), not from `next.payload`.
- Result post: the claim message goes to `done`. A new message holds the scrubbed reply text and the `artifacts`. If there is a next agent step, it also holds `next`, `hop + 1`, and the mention. If the next step is a human approval, the new message is the approval request with a button (D11). If there is no next step, the thread is done.
- A step is done when its agent posts `status: done` in the thread (the general rule). The core has no step-type code: a review step is a normal step.
- Rationale: FR-011, FR-012, FR-013.

### D9. Run request and the `claude` mapping (FR-022, FR-027, SC-009; Q5 = a)
- Confirmed by the owner (2026-11-26): the planner always runs as `RunRequest((), "read", False)`, with no file tool, also for the owner. A step loads only its own capability (`capabilities` has the one ID of the step).
- Decision, core: the pure function `build_run_request(step, starter, owner)` returns `RunRequest(capabilities, access, requester_is_owner)` (`src/pipe/core/runrequest.py`).
  - A bot step with `access: read`: `capabilities = (step.capability,)`, `access = "read"`, `requester_is_owner = bool(owner) and starter == owner`. An empty `owner` gives `false` (fail closed).
  - The planner call: the planner code builds `RunRequest((), "read", False)`. No capability and no owner rights give no file tool.
  - `access: approve` raises `ValueError` (an approval step runs no runtime). `access: write` raises `ValueError` (not supported before spec 004). `validate_plan` refuses both cases first.
  - The function names no tool, no flag, and no runtime.
- Decision, `claude` adapter: the pure function `map_request(request, caps, exposed, claude_cfg)` returns `StepTools(policy, load)` (`src/pipe/runtime_claude_request.py`). `claude_cfg` is the `runtime.claude` config section (`owner_tools`, `repo_roots`, `deny_rules`).
  - `load = load_set(caps, exposed, request.capabilities)` (002 D16). Only exposed items load. A capability that is not exposed now is skipped, and the run fails with `reason: capability not available`.
  - `requester_is_owner` true: `tools = runtime.claude.owner_tools` (default `Read`, `Grep`, `Glob`). `requester_is_owner` false: `tools = []` and `allowed = []`. The `Skill` tool and the per-skill rules come from `prepare` (002).
  - `access: read`: the write tools `Edit`, `Write`, and `NotebookEdit` are removed from `tools` and added to `disallowed`. This makes `read` mean no file writes, also when the owner widened `runtime.claude.owner_tools`.
  - `disallowed` = `mcp__<server>` for each `owner-only` MCP server, `Skill(<name>)` for each `owner-only` skill or command, the write tools (for `read`), and every entry of the effective deny list (`Bash(git push:*)` always, plus `deny_rules`; the owner cannot remove the default). The list is defense in depth. An `owner-only` item is never in the load set.
  - `access: write` raises `ValueError`. The adapter turns it into `RuntimeFailed`.
  - `restricted` is always `True`. `--permission-mode dontAsk` stays (001).
  - `runtime_claude.run(inp)` calls `map_request`, `prepare` (002), `build_cmd`, the child process, and `cleanup` in a `finally`. The stepper and the planner know none of this.
- Without `inp.request` the 001 path applies (`tools_for`). This equals a request with no capability, access `read`, and `requester_is_owner` set by the sender: the 001 behavior is a special case.
- Rationale: 002 says that 003 sends capability IDs and an access level. FR-022 says that a step that another person started loads exposed capabilities only and gets no file tool. Principle XI keeps tool names in the adapter.
- Ceiling: a skill that needs files outside its own directory can fail (002 D6 ceiling). The syntax `Bash(git push:*)` is not checked (A3).

### D10. Offline wait (FR-017)
- Decision: after the sender posts a handoff to an agent step, it starts a timer of 60 seconds (constant `OWNER_OFFLINE_AFTER_S`). When the timer fires, it re-reads the thread. If no valid claim for that step exists, it posts a `waiting` message (`reason: owner offline`, access and step of the waiting step). "Owner offline" means "the owner adapter did not claim the step" (spec Assumptions). The wait time is the difference between the `ts` of the `waiting` message and the `ts` of the first later claim of the same step. `pipe metrics` computes it. No extra field is stored.
- Ceiling: the timer is in memory. If the sender stops in the 60 seconds, no `waiting` message appears. The next agent still runs the step when it starts (001 catch-up).
- A `waiting` message is allowed from the assigned agent, or from the agent of the step before (the planner for step 1).

### D11. Approval step, button, and retry (FR-013, FR-015)
- Decision: a button is a Block Kit `actions` block with `action_id` `pipe_approve` or `pipe_retry`. Slack sends the click to the app that posted the message (Socket Mode `block_actions`). The adapter reads the thread, then calls `route` with a click event. A click counts only from the thread starter or the owner of the agent that posted the button (constitution V). On approve: the message goes to `done`, the button is removed, and the thread is `done`. On retry: the failed message loses its button, and the stepper starts a new claim for the same step with the same `hop` (no increase).
- Rationale: FR-006, FR-007, FR-015, FR-016. A retry is a click, never automatic.
- Alternative: reactions for approve and retry. Rejected: the brief says "button".

### D12. Timeout and an adapter that is down (Q4 = a)
- Decision: the runtime wrapper kills the child at `step_timeout_min` (001) and raises `RuntimeFailed("timeout")`. The stepper then updates the claim message to `failed`, `reason: timeout`, with a "Retry" button, in less than one minute (SC-006). At start and at each reconnect, the adapter runs a `wake` pass: each own step whose `step_status` is `claimed` or `running` and which is not in the in-flight set goes to `failed` with `reason: interrupted` and a "Retry" button. While the adapter is down, the step stays `running`. No other adapter changes it. No retry is automatic (FR-016).
- Rationale: only the process that can run the step changes its state. A step that is `running` while the laptop is off is a known limit; the metric "median wait" does not count it. The upgrade trigger "steps often wait" (brief §10) covers it.
- Alternatives: any adapter fails a stale step after the limit plus a grace time; the planner adapter watches all steps. Both were rejected by decision Q4 = a.

### D13. Catch-up (FR-018, FR-019)
- Decision: reuse the 001 catch-up (`parents_to_scan`, `pick_missed`, dedupe by `event_id` and mention key, in-flight set). The adapter runs it on `#pipe-work` and on the channels of 001. For each thread with new messages, it builds `ThreadState` and synthesizes the same events that a live path would send (human message, bot message, reaction, wake). It calls `route` for each. Because a handoff has a mention of the next agent, `pick_missed` finds it. `route` also keeps the check "no claim by self after this handoff", so a repeat gives no second run. A ✅ that was added while the adapter was down is read from the `reactions` field of the plan message.
- `last_seen_ts` advances after the step ends (`done`, `failed`, or refused), as in 001.
- Changes to 001: `pick_missed` must pass bot messages that have task metadata to `route` (the 001 rule "ignore a message with `bot_id`" stays for plain chat). T055 lists the change.

### D14. Dependencies
| Dependency | Why |
|---|---|
| `slack_bolt`, `pyyaml` (already in 001) | Socket Mode and config. |
| stdlib `urllib`, `json`, `statistics`, `threading`, `datetime` | GitLab read, median, step timers, week grouping. |
| `pytest` (dev only, already in 001) | Tests. |

No new dependency.

### D15. Slack scopes and events (new in 003)
- New bot scope: `reactions:read` (the `reaction_added` event and the `reactions` field). 003 does not add `users:read` (Q7 = b: the card holds `bot_user_id`). `chat:write` covers `chat.delete` of the bot own message. Existing: `channels:history`, `channels:read`, `metadata.message:read`, `app_mentions:read` (001), `pins:read` (002). For a private `#pipe-work` add `groups:history`, `groups:read`.
- New event subscription: `reaction_added`. New setting: Interactivity on (Socket Mode needs no request URL).
- `pipe metrics` needs the bot token scopes `channels:history`, `reactions:read` (already listed).

### D16. Planner (FR-002 to FR-005)
- Decision: [contracts/plan-schema.md](contracts/plan-schema.md). The prompt has a fixed instruction, the card list (name, `bot_id`, capability IDs from `skills[].id`, and descriptions), and the human request as untrusted data. The runtime adapter gets `RunRequest((), "read", False)` (no capability, not owner), which gives `--tools ""`, and `--json-schema` for the plan. `validate_plan` checks the result in code. A runtime failure or a bad plan gives one `failed` plan message with the reason. There is no automatic re-plan. The person writes a new top-level message to try again.
- Edge cases: a person who edits the request after the plan does not change the plan (the plan is the metadata of the plan message, and no `message_changed` event is used). A ✅ on any message other than a plan with `status: needs_approval` is ignored. A second ✅ after the start is ignored (the start message exists).

### D17. Metrics script (US6, FR-023)
- Decision: `pipe metrics [--weeks N]` reads `conversations.history` and `conversations.replies` of `#pipe-work` with metadata and reactions. It keeps only trusted task messages (D4). It reads the state of each link in `artifacts` through `MrStatePort.mr_state(url)`. The port is replaceable. The first provider is `src/pipe/gitlab_io.py`: it calls the GitLab API (`GET /api/v4/projects/<path>/merge_requests/<iid>`, header `PRIVATE-TOKEN`) and maps the answer to `{state: open|merged|closed, merged_at}`. The host of the URL must equal the host of the provider config `mr_state.gitlab.url`; other hosts are skipped (the token never goes to another host). The token comes from the Keychain (`mr_state.gitlab.token: keychain:<service>`, account `token`). The core knows only the normalized state. The pure function `compute_metrics` returns four values (definitions in [data-model.md](data-model.md) "Metrics"). The script prints one line per metric with the brief §10 threshold.
- A "useful delegation between owners" is a step with an MR URL in `artifacts` whose agent owner is not the thread starter and whose MR state is `merged`. It counts in the week of `merged_at`. (Spec 004 adds `delegate` steps. The same rule covers them.)
- Rationale: FR-023: Slack and an MR-state provider only, no database.

### D18. Testing
- `pytest`. Unit tests for each `core/` module are written first (principle VII). `make_thread(...)` in `tests/fakes.py` builds a `ThreadState` and a fake `#pipe-work` channel from a short table (messages, cards, reactions). Integration tests with fakes cover the flows listed in the plan. One stub-`claude` test checks that the planner command has `--json-schema` with the plan schema and `--tools ""`, and that a foreign-started step command has `--plugin-dir` and no `Read`. The import-boundary test (`test_core_boundary.py`) reads the source of the core modules with `ast`. No test calls real Slack, real GitLab, or a real LLM.

### D19. Capability-agnostic core and the `RunRequest` extension (principle XI, FR-024, FR-027)
- Decision: the pipeline core (`core/pipeline.py`, `trust.py`, `claim.py`, `route.py`, `runrequest.py`, `render.py`, `metrics.py`) uses `capability_id` strings from the cards and nothing else about capabilities. It gives the runtime `RunRequest{capabilities, access, requester_is_owner}` as the new field `RuntimeInput.request`. 001 `RuntimeInput.tools` stays for the 001 chat path. When `request` is set, the runtime adapter builds the tool policy itself (D9). This extends the 001 runtime contract by one optional field. Spec 001 is not changed by this plan. See [contracts/runtime-request.md](contracts/runtime-request.md).
- The import-boundary test (T071) enforces the rule: no core module imports a runtime-specific or transport-specific module (`pipe.runtime_claude*` (this includes `pipe.runtime_claude_tools` and `pipe.runtime_claude_discovery`), `pipe.runtime_exec`, `pipe.runtime_http`, `pipe.runtime_select`, `pipe.declared`, `pipe.gitlab_io`, `pipe.transport_slack`, `pipe.transport_slack_events`, `pipe.transport_slack_map`, `pipe.transport_slack_http`). The test covers the 003 core modules and the 002 core modules (`capability`, `exposure`, `card`, `summary`, `schema`), and no core module holds a runtime tool name or the terms plugin, MCP, wiz-review, or GitLab in code or in string constants.
- Rationale: one agent stack must not shape the core. A new runtime or a new review tool needs no core change.

### D20. Task message fields: `phase` and `access`
- Decision (confirmed by the owner, 2026-11-26): `pipe.task.v1` has no field `kind`. The name `kind` belongs to the agent card only. `phase` (`plan` or `step`) tells a plan-phase message from a step message. `access` (`read`, `write`, `approve`) is the access level of the step, present on step messages only. `next` is `{agent, access, payload}`. The capability and the goal of a step come from the plan, not from the message.
- The step types `review`, `delegate`, and `status` are gone. What a step does comes from its capability. A delegation is a step with `access: write` (spec 004).
- Rationale: the smallest change that removes the name `kind` and keeps the trust checks of D4.

### D21. Config sections for the runtime adapter and the MR-state provider
- Decision: the `claude` adapter keys sit under `runtime.claude`: `owner_tools` (default `Read`, `Grep`, `Glob`), `repo_roots` (default `[~/code]`), and `deny_rules` (default `[]`: extra rules; `Bash(git push:*)` is always denied, spec 001 FR-019). The key `runtime.name` defaults to `claude` (the only value in 003). The core never reads this section. The provider keys sit under `mr_state`: `mr_state.provider` (default `gitlab`) and `mr_state.gitlab.url`, `mr_state.gitlab.token`. They are the only keys for the MR-state provider.
- Spec 001 defines `owner_tools`, `repo_roots`, and `deny_rules` under `runtime.claude` (aligned on 2026-11-26). 003 adds `runtime.name` only. The loader has no fallback for the old top-level keys: they are an error (001).
- Rationale: the brief §5.4 moves these keys under the runtime adapter. They are not core concepts.

### D22. Late binding by tag (owner decision 2026-11-26)
- Decision: a plan step may have `agent: any` and `capability: tag:<tag>`. `validate_plan` checks that at least one trusted card has an exposed entry with the tag and a fitting access (rule 11). The start or result message of the previous step mentions every eligible agent (`Transport.mention` of each card `bot_user_id`). Each eligible adapter runs `route`: `BotMessage` with `next.agent: any` gives `claim` when its own card matches (`matches_tag`). The claim contest of D7 decides: the lowest `ts` wins. The winner calls `bind_step` to turn the tag into one of its own capability IDs (the lowest exposed ID with the tag and a fitting access). It then runs as for a fixed step. For a `write` step the 004 gate runs for the winner (per claimer: its allowlist and its owner).
- Access fit (LB1): the access of the step fits a card entry when the entry has no `access` or both are equal. Rationale: a declared capability cannot enforce `read` inside the command, so a loose rule ("write covers read") would run a write-capable tool in a read step. Alternative (a `read` step fits `write` entries) rejected for now.
- After the claim, only the winner posts later messages for the step. `check_task_msg` uses `step_agent`. A human step after a tag step may name only the thread starter (the agent is unknown at plan time).
- No claimer (LB3): the sender of the handoff starts a timer of `step_timeout_min` (injected factory, as in D10). When it fires, the sender reads the thread. If no valid claim exists, it posts type 9 (`failed`, `no_claimer`) with a "Retry" button. "Retry" (thread starter or the owner of the sender) posts the handoff again with the same `hop`. A tag step gets no `waiting` message at 60 seconds: no single owner is known.
- Ceiling: the timer is in memory (as in D10). If the sender stops, no type 9 message appears. A restart (`Wake`) of the sender does not post it either. A person starts a new thread. Known limit.
- Ceiling: a rejected `write` claim is final (004 DQ7). Other eligible agents do not get a second chance.
- Rationale: the planner needs no knowledge of who is online. The existing claim rule needs no change. Rejected: the planner picks one eligible agent (no late binding); a "claim window" with a priority list (more rules).

### D23. Runtime selection and the `exec` and `http` adapters (owner decision 2026-11-26)
- Decision: `pick_runtime(caps, capability_id, default)` (core, pure) returns the `runtime` of the local capability. `runtime_select.py` implements `RuntimePort` and calls the adapter that the function names. `runtime_exec.py` and `runtime_http.py` implement `RuntimePort` ([../001-adapter-core-status/contracts/runtime-exec-http.md](../001-adapter-core-status/contracts/runtime-exec-http.md)). They read the declared entry (spec 002 data-model "Declared capability") by capability ID, and the `exposed` list.
- Security (each is a test): the adapter runs a declared capability only when it is exposed now (also for a step that the owner started); the `exec` child gets an argv list (no shell), an empty working directory, and only the variables of `env_allow` plus `PIPE_RUNTIME=1`; the `http` token comes from the Keychain by name and goes only to the configured URL, with no redirect; no log line, reason, or text holds a command line, URL, token, or environment value; output `text`, `reason`, and `artifacts` pass `scrub`, and `text` passes `escape_mentions`; the result is at most 1 MB; the run has a timeout.
- Rationale: a new tool needs config only. The core stays unchanged. Rejected: run the command through the `claude` adapter (it would put the command under `claude` tool rules and hide it from the core).

### D24. Payload and result schemas (FR-032, FR-033)
- Decision: `check_input(step, cap)` validates `payload` (missing = `{}`) against `cap.input_schema` with `validate_schema` (spec 002 D20). The stepper calls it after the claim contest and before the gate (so an owner is not asked about work that cannot run). It uses the local capability of the claimer, not the card (the card can be stale). `check_output(output, cap)` validates `RuntimeOutput.data` against `cap.output_schema` after the run. A missing `data` with a schema is `invalid_result`. The reason is a fixed word (`invalid_payload`, `invalid_result`). The message text may add up to 3 error sentences. They hold the path and the rule, never the value.
- `output_schema` goes to the adapter in `RunRequest.output_schema`. The `claude` adapter merges it into `--json-schema` as the schema of `data`. The `exec` and `http` adapters send it in the input. Without a schema nothing changes.
- A failed step has a "Retry" button as for any failure. The same payload fails again: the person starts a new plan. Known limit.
- Validator: spec 002 D20 (stdlib subset, no `jsonschema`).

### D25. Plan source and hop limit by source (constitution 1.3.0, owner decision 2026-11-26; 006 DQ1 = b, DQ10 = a)
- Decision: `pipeline.source` is `template:<name>@<hash>` or `free`. It is a claim, never a fact. `effective_source(plan, flows, cards, starter)` (`core/source.py`, pure) gives `template` only when this adapter has a template of that name, the hash of the parsed file is equal, and `Flow.matches(steps, cards, starter)` is true (spec 006 owns `Flow`). Else `free`. The limit is `hop_limit(effective)`: 3 or 5. `validate_plan` and `route` both call it. The refusal text gets the suffix ` (plan source not verified)` when the declared source is a template and the effective source is `free` (fail closed, also when two team members have different template files).
- Rationale: principle V and the constitution rule of 1.3.0. A bot with a card can write any text in a plan message. A receiver must not raise its own limit because a message says so. The check needs no new config and no new trust path.
- Rejected: trust the claim (a modified planner raises the limit); a hash allowlist in the owner config (more config, add later if a second control is wanted).
- Ceiling: a bad template that the team merged in git passes the check. The review of `flows/` is the control. Every `write` step still meets the spec 004 gate and the human ✅.

### D26. Dialog step (owner decision 2026-11-26; 006 DQ7 = a)
- Decision: a runtime result `waiting` with `reason: needs_input` ends the run. The stepper posts a type 10 message (the question, mentions the thread starter) and starts a dialog timer (`dialog_timeout_h`, default 24, injected factory). A thread reply that mentions the agent, from the thread starter or the card owner of the agent, gives the route action `resume`. The stepper runs the SAME step with the SAME `RunRequest` and `task`. The thread (with the question and the answer, as untrusted text) is the only new input. No claim, no `hop` change. The type 10 message is the status message of the step: `waiting`, then `running`, then (after the result) the later type 5 message is the status. Expiry: `Wake` and the timer give `expire_dialog`: type 10 goes to `failed`, `dialog_timeout`, with "Retry".
- The step timer (`step_timeout_min`) is the kill timer of the runtime child. It runs only while a child runs. So it is paused while the step waits, with no extra code. Each resume gets a full timer.
- Why a mention: the Slack transport reads `app_mention` only (001 D5). A reply without a mention gives no event. Alternative: subscribe to `message.channels` (open question U3).
- Why a type 10 message and not an update of the claim: a new message has its own `ts`, so the core can tell "the answer came after the question". An in-place update does not notify the person.
- `Wake` rule change: the interrupt rule reads `step_status` (the latest message of the step), not each message. A waiting question is not interrupted.
- Ceiling: the timer is in memory. `Wake` recomputes the expiry from the `ts` of the question, so a restart does not lose it.

### D27. Context for the next step (owner decision; 006 FR-025; 005 DQ2 extended)
- Decision: `effective_payload(step_payload, results)` adds `context` (a list of `{step, text, artifacts}` of all done steps) and `artifacts` (all links) to the step payload. The plan payload wins on a key clash. Limits: 1000 characters for each `text`, 4000 in total. Large context goes by link (`Transport.upload_file`, spec 001 FR-024). Step 0 gets no key. `check_input` validates the effective payload (default U4).
- Rationale: one small pure function. The core stays generic: a capability reads `context` or `artifacts` if it needs them.

### D28. Plan proposal and gate (owner decision; 006 DQ6 = a, DQ12 = a)
- Decision: a gate and a proposal use ONE path: a type 5 message with `needs_approval`. A ✅ from the thread starter or the owner of the planner on that message gives `release`. The author adapter then posts what the step would have posted without the gate. A step never starts work by itself: the next step starts only from the released result. A proposal must pass `validate_plan` (free, limit 3) or the step ends `invalid_proposal`. An approved proposal is context only, in a template and (default U2) in a free plan.
- Rationale: it reuses the ✅ rule and one status. A proposal that starts work would be a new execution path. It needs an owner decision (U2).

### D29. `exclude_agents_of` (owner decision; replaces the general rule of 005 DQ8)
- Decision: an optional step field. The claim rule ignores a claim from an agent that holds an excluded step (`claim_excluded`, in `route` and `check_task_msg`). `validate_plan` rejects the plans that certainly have no claimer (`exclusion_deadlock`). Else the step ends `no_claimer` at run time. The planner sets the field for a step that reviews or checks earlier work. The core does not know what "review" means: the planner prompt (outside the core) says it.

### D30. `on_fail` (owner decision; 006 DQ5 = a, DQ11 = a)
- Decision: at most ONE `on_fail` per plan. The target is the last step. It is skipped on success. It runs only when the source step ends `failed` with `reason: run_failed` (the runtime returned `status: failed`). The branch is a type 11 message: `failed` with `next`, `hop + 1`, no button. The flow ends after the branch step. A timeout, `no_claimer`, `invalid_*`, `dialog_timeout`, `rejected`, `interrupted`, and a `RuntimeFailed` use "Retry". A free plan may use the field (limit 3).
- Rationale: a timeout is an infrastructure fault. A branch would hide it. A loop is impossible: the target is later and last.
- Known limit: an `exec` capability whose command exits non-zero gives `RuntimeFailed("exit <code>")`, not `run_failed`. A capability that wants the branch returns `status: failed` in its JSON (U7).

### D31. New message types and trust (owner decision)
- Decision: type 5 gets `needs_approval`. New type 10 (dialog question) and type 11 (branch handoff). New route actions `plan_flow`, `release`, `resume`, `expire_dialog`. Each type has a check in `check_task_msg` through `step_agent`: only the agent that won the claim can post for the step. See contracts/task-metadata.md rule 7.

### D32. Rejected `write` tag step (decided, deferred)
- Decision: a rejected claim ends the step `failed`, `rejected`, with no "Retry". No other eligible agent gets a second claim. `route` ignores any later claim or `Wake` claim for a step whose latest claim is `failed` with `reason: rejected` (`step_rejected`). Why: `resolve_claim` drops `failed` claims, so without this rule an agent that restarts could claim the step again.

## Cannot verify on this machine

- A1: that Slack sends `app_mention` for a message that another bot posted with a mention of this app. If not, subscribe to `message.channels` (and `message.groups`) and let `route` match `next.agent == self` (D5). `route` does not change. Check in the manual run.
- A2: that `conversations.replies` returns `metadata` (with `include_all_metadata`) and `reactions` for bot messages, and that a click payload (`block_actions`) has the channel, the message `ts`, and the user. A `reaction_added` event has only the item `ts` (no `thread_ts`), so the adapter calls `conversations.replies` with the item `ts`; Slack accepts the `ts` of a reply there (to check). No Slack access here.
- A3: the exact `--disallowedTools` syntax `Bash(git push:*)` (the always-present default of the effective deny list) and the effect of `Skill(<name>)` deny rules. Check with a real `claude` run (task T067).
- A4: the Slack limit for the size of `metadata`. A plan with 3 steps and goals of 500 characters each is below 2 KB.
- A5: `chat.delete` of the own message needs only `chat:write`.
- A6: the GitLab API shape (`state`, `merged_at`) of a merged MR and the project path encoding. Check with a real merged MR in the manual run.
- A7: the 002 load flags for a step with a capability that is not in the generated plugin (002 A3 to A5). Same checks as 002.
- A8: that a bot message in `conversations.history` carries `user` equal to the bot user ID (the Slack adapter maps it to `sender_handle`), so `trusted_cards` can compare it with `bot_user_id` (D3). If the field is missing, only the lower-`ts` rule applies. Check in the manual run.
- A9: that a thread reply that mentions the agent reaches the agent as `app_mention` (the dialog answer, D26). It is the same event as for any mention, so it should. Check in the manual run.
- A10: the Slack limit for the size of `metadata` with a proposal (4000 characters as canonical JSON) in the type 5 message (A4 covers the plan).
