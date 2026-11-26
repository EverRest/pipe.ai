# Data Model: Pipelines from Chat

All entities are frozen dataclasses in `src/pipe/core/`. The pipeline state is not stored in a file. It lives in the thread messages (`pipe.task.v1` metadata). No database. Spec entities: Pipeline, Step, Task state, Claim, Agent card (from 002).

## Config keys added by 003
File: `~/.pipe/config.yaml`. `step_timeout_min` exists from 001. The core reads only `work_channel` and `step_timeout_min`. The two sections below are read by the adapter code outside the core.

| Key | Type | Rule |
|---|---|---|
| `work_channel` | str | Default `pipe-work`. |
| `dialog_timeout_h` | int | Default 24. Minimum 1. Maximum 168. The longest time that a dialog step (a type 10 question) waits for an answer (FR-036). The core reads it (like `step_timeout_min`). After it, the step is `failed` with `reason: dialog_timeout`. |
| `runtime.name` | str | Default `claude`. The default runtime adapter (planner, chat, and a step with no capability). One of `claude`, `exec`, `http`. A capability picks its own adapter with its `runtime` (FR-034). |
| `runtime.claude.owner_tools` | list[str] | Default `[Read, Grep, Glob]`. Tools of an owner-started step. Defined by spec 001. Read by the `claude` adapter only. |
| `runtime.claude.repo_roots` | list[str] | Default `[~/code]`. File confinement. Defined by spec 001. Read by the `claude` adapter and by 002 discovery. |
| `runtime.claude.deny_rules` | list[str] | Default `[]`. Extra deny rules. `Bash(git push:*)` is ALWAYS denied (the owner list only adds). Defined by spec 001 (FR-019). Read by the `claude` adapter only. |
| `mr_state.provider` | str | Default `gitlab`. The only value in 003. |
| `mr_state.gitlab.url` | str? | Optional. `https://` URL of the GitLab host. Needed only by `pipe metrics`. |
| `mr_state.gitlab.token` | str? | Optional. Format `keychain:<service>`. A plain token (`glpat-...`) is rejected. Needed only by `pipe metrics`. |

Spec 001 defines `runtime.claude.owner_tools`, `runtime.claude.repo_roots`, and `runtime.claude.deny_rules`. 003 adds `runtime.name`. The old top-level keys are an error (001). The core never reads the `runtime` section.

Constants in code (not config): `MAX_HOP_FREE = 3`, `MAX_HOP_TEMPLATE = 5`, `CLAIM_SETTLE_S = 2`, `OWNER_OFFLINE_AFTER_S = 60`, `MAX_GOAL_CHARS = 500`, `MAX_CONTEXT_TEXT = 1000`, `MAX_CONTEXT_TOTAL = 4000`, `MAX_PROPOSAL_CHARS = 4000`. There is no fixed `MAX_HOP`. The limit comes from `hop_limit(effective_source)` (`core/source.py`, FR-042).

## Names in this spec (transport-neutral)
The wire fields keep their names: card `bot_id`, `bot_user_id`, `owner`, and the task field `by`. The core reads them as opaque ids. For every message and event, the core rules use the neutral fields of spec 001 ([contracts/transport.md](../001-adapter-core-status/contracts/transport.md)): `sender_id`, `sender_is_bot`, `sender_handle`. The card owner is `card_owner_id`. In the rules below, "the author" means `sender_id`, and "the author is a bot" means `sender_is_bot` is true. `by` must equal `sender_id`. The card `bot_user_id` must equal `sender_handle` (when it is present).

## Step
| Field | Type | Rule |
|---|---|---|
| `agent` | str | `<bot_id>`, `human:<user_id>`, or `any` (a tag step, below). |
| `capability` | str? | A `capability_id` from the card of `agent` (002 card `skills[].id`), or `tag:<tag>` when `agent` is `any`. Required for a bot step. Absent for a human step. The core treats an ID as an opaque string. A tag matches `^[a-z0-9-]{1,32}$`. |
| `access` | enum | `read` or `approve` in 003. `write` is an error in a plan in 003 alone (spec 004 accepts it). `read`: no file writes. `approve`: a button, no runtime. |
| `goal` | str | Non-empty. At most 500 characters. Passes `scrub`. |
| `payload` | object? | Optional. A JSON object, at most 2000 characters as canonical JSON. Only on a bot step. The core carries it and, when the claimer's capability has an `input_schema`, validates it before the run (FR-032). A missing `payload` counts as `{}`. |
| `exclude_agents_of` | tuple[int]? | Optional (FR-039). Indexes of earlier BOT steps. At most 5. Only on a bot step. |
| `gate` | `"approval"`? | Optional (FR-043). Only the value `approval`. Only on a bot step. |
| `on_fail` | int? | Optional (FR-040). The index of the branch step. At most one step per plan. Only on a bot step. |
| `target` | str? | Added by spec 004. Optional, at most 64 characters, only on a `write` step. An opaque name of a repo. The core carries it and never reads it. `validate_plan` does not check it. Not used in 003 alone. |

A plan step has no field `skill` and no field `kind`.

## Pipeline (plan)
`{ "steps": [Step, ...], "source": "free" }`. Stored in the `pipeline` field of the plan message. `source` is `free` or `template:<name>@<hash>` (`<name>` matches `^[a-z0-9-]{1,32}$`, `<hash>` is 32 lower-case hex characters). A missing `source` means `free`. The planner core writes it. The LLM never does (FR-042). Rules (`validate_plan`, all in one pure function):

1. `steps` is not empty. At most `hop_limit(effective_source)` steps have a bot agent: 3 for a free plan, 5 for a verified template (Q2 as changed by N7, FR-042).
2. Each `access` is `read` or `approve`. `write` is an error: `not supported before spec 004`. Any other value is an error.
3. A bot agent step needs `access: read` and a `capability`. A `human:<user_id>` step needs `access: approve` and no `capability`. `payload` on an `approve` step is an error.
4. An `approve` step can only be the last step. There is at most one.
5. Each bot agent that is not `any` has a trusted card (`cards[bot_id]`).
6. For a step that is not a tag step, the `capability` is in `cards[agent].skills[].id`, and `access_fits(step.access, entry.access)` is true. The card lists exposed capabilities only, so a hidden capability is an error. An unknown agent gives no capability check (rule 5 reports it).
7. `goal` is not empty and has at most 500 characters.
8. A human step: the user is the thread starter or the owner of the bot agent of the step before it (Q3 = a). This rule needs the `starter` argument.
9. The first step is a bot step (a plan cannot start with a human step).
10. Tag steps (late binding): `agent: any` needs `capability: tag:<tag>`, and a `tag:` capability needs `agent: any`. A tag step is a bot step: it counts for the limit of 3 and cannot be `approve`.
11. For a tag step, `matches_tag(card, tag, access)` is true for at least one trusted card. Else the error is `step N: no agent offers tag <tag>`. The card side sees only `skills[].tags` and `skills[].access`.
12. Rule 8 for a human step after a tag step: only the thread starter qualifies (the agent is not known at plan time). The owner of the step before is not used.
13. `exclude_agents_of` (FR-039): each item is an integer lower than the step index, names a bot step, and appears once. At most 5 items. The field is on a bot step only.
14. Exclusion check (`exclusion_deadlock`): a fixed step whose `agent` equals the fixed agent of an excluded fixed step is an error (`step N: agent X holds excluded step M`). A tag step is an error when every trusted card that matches its tag is the fixed agent of an excluded fixed step (`step N: no agent can claim after exclusion`). A tag step with an excluded tag step gives no error here (the holder is unknown at plan time).
15. `gate` (FR-043): the value is `approval`, and the step is a bot step.
16. `on_fail` (FR-040): at most one step has it. Its value is the index of the LAST step. The step that has it is not the last step. The last step is a bot step with no `on_fail`. The plan has no human step. A step with `on_fail` has an index lower than the target (no loop, no jump back).
17. `source` has the form above, else the error `bad source`. `validate_plan` works out `effective_source(plan, flows, cards, starter)` (`flows` is `None` or empty: always `free`). A declared template that is not verified gives no error by itself. The limit of rule 1 is then 3.
18. A proposal (FR-038) goes through the same function as a plan with `source: free`, `flows` empty.

Pure helpers in `core/pipeline.py`:

- `access_fits(step_access, cap_access)`: true when `cap_access` is `None`, or when both are equal (decision LB1).
- `matches_tag(card, tag, access)`: true when one `skills[]` entry has `tag` in `tags` and `access_fits(access, entry.access)`.
- `bind_step(step, caps, exposed, tag_map)`: for a tag step, returns the step with `capability` set to the lowest ID among the own capabilities whose state is `exposed`, whose tags (`resolve_tags`) hold the tag, and whose access fits. It returns `None` when none exists. A fixed step is returned as it is.
- `claim_excluded(plan, thread, i, agent_id)` (core/claim.py): true when the plan step `i` has `exclude_agents_of` and `step_agent(thread, j) == agent_id` for one `j` in it.
- `branch_target(plan, i, reason)`: `plan.steps[i].on_fail` when `reason == "run_failed"`, else `None`.
- `next_step(plan, thread, i)`: the index of the step after step `i`. It is `None` after the last step. It is also `None` when the next index is the branch target (the branch step is skipped on success). After a branch handoff for step `i`, it is the branch target.
- `gate_pending(thread, i)`: true when the latest trusted message of step `i` is a type 5 with `needs_approval` and no later `done` message of step `i` exists.
- `open_question(thread)`: the latest trusted type 10 message with `status: waiting` that has no later message for its step, or `None`.
- `dialog_expired(question_ts, now, hours)`: true when `now` minus the `ts` of the question is greater than `hours` hours.
- `flow_word(text)`: the name of the first word `flow:<name>` (`<name>` matches `^[a-z0-9-]{1,32}$`, the word ends at a space or at the end of the text), or `None`. Spec 006 `parse_flow_mention` does the full parse.
- `step_agent(thread, i)`: the agent of step `i`: the plan agent for a fixed step, or the `by` of the winning claim (`resolve_claim`) for a tag step. It is `None` before a claim.

`validate_plan(plan, cards, starter=None, flows=None) -> list[str]`. (The owner shorthand `validate_plan(plan, cards, flows)` means this function. `starter` stays the third argument.) Each error is a fixed sentence with the step number, for example `step 2: agent B123 has no card`. An empty list means the plan is valid. Rule 8 is skipped when `starter` is `None`. The function reads no tag, no type, and no name of a capability. A review step passes like any other step.

## TaskMsg (`pipe.task.v1`)
The `event_payload` of a thread message. Brief §5.2, FR-020.

| Field | Type | Rule |
|---|---|---|
| `v` | int | 1. |
| `task_id` | str | Equals the `thread_ts`. |
| `phase` | enum | `plan` (plan, rejected plan, start handoff) or `step` (claim, result, approval request, waiting, hop refusal). |
| `access` | enum? | `read`, `write`, or `approve`. Required when `phase` is `step`. Absent when `phase` is `plan`. The parser accepts `write`. `route` ignores a `write` step in 003. |
| `status` | enum | `needs_approval`, `claimed`, `running`, `waiting`, `done`, `failed`. `needs_approval` also applies to a step claim (type 4) of a `write` step after spec 004 (owner gate), and to a type 5 result with a gate or a proposal (FR-043, FR-038). `waiting` also applies to a type 10 dialog question (FR-036). A step that is `failed` with `reason: rejected` has no "Retry" (spec 004). |
| `by` | str | Id of the author (a card `bot_id`). Must equal the message `sender_id`. |
| `hop` | int | 0 or more. |
| `pipeline` | Pipeline? | In the plan message. Also in a type 5 message with `needs_approval` (a proposal, FR-038). |
| `step` | int? | Index of the step that the message is about. In a plan message it is 0 (the first step to run). |
| `next` | `{agent, access, payload}`? | `payload` is `{"step": <index of the next step>}`. `access` is the access of the next step. A type 11 message (`failed`, `reason: run_failed`) carries `next` for the branch step (FR-040). No other `failed` message has `next`. |
| `artifacts` | list[str]? | Links such as MR URLs. Each is an `https://` URL. |
| `reason` | str? | Scrubbed. At most 200 characters. Fixed values include `timeout`, `interrupted`, `owner offline`, `hop limit exceeded` (with the suffix ` (plan source not verified)` when a declared template is not verified), `capability not available`, `no_claimer`, `invalid_payload`, `invalid_result`, `needs_input` (on a type 10 `waiting`), `dialog_timeout`, `run_failed`, `invalid_proposal`, and (spec 004) `rejected`. `run_failed` means that the runtime returned `status: failed`. A runtime exception (`RuntimeFailed`: exit code, http code, bad output) keeps its own reason and does not branch. |

The field named `kind` is not in the payload. In the agent card, `kind` is `agent` or `trigger` (spec 002).

`parse_task(message) -> TaskMsg | None` returns `None` when a field has a wrong type or value. Field-level trust checks are in `check_task_msg` (research.md D4).

`TaskMsg` also keeps `ts` (the message `ts`, string), `sender_id` (the author), and `reactions` (list of `{name, users}`). They come from the transport, not from the payload.

## Status of a step and of a thread
`step_status(thread, i)`: the `status` of the latest trusted message (by `ts` as numbers) with `step == i` and `phase == step`. A message from a lost claim is deleted, so it never counts. If no message exists, the step is `pending`.

The status message of a step is its latest trusted message. A dialog question (type 10) is the status message while the step waits. In-place changes (`running`, `failed`, the "Retry" button) apply to the status message.

`thread_status(thread)` returns one of:

```text
rejected       the plan message has status failed
needs_approval the plan message has status needs_approval and no start message exists, OR the current step has a pending gate (gate_pending)
running        the start message exists and the last step is not done
done           the last step is done (agent step: step_status done; approve step: approval message done)
failed         the current step is failed (also for hop limit exceeded)
waiting        the current step is waiting
```

The current step is the lowest step that is not `done` and is not `branched`. A step is `branched` when a type 11 message exists for it. The branch step is the current step after that. The branch step is skipped on success: the last bot step before it ending `done` makes the thread `done` (`next_step` gives `None`). After the branch step ends `done`, the thread is `done`. After it ends `failed`, the thread is `failed`. A "Retry" is not offered for a branched step.

## Claim
A step claim message. `resolve_claim(claims) -> Claim | None`.

| Field | Type | Rule |
|---|---|---|
| `ts` | str | `ts` of the claim message (transport format: seconds, a dot, six digits). |
| `by` | str | `bot_id`. |
| `status` | enum | `claimed`, `running`, `done`, `waiting`, or `failed`. |

Rules:
1. Claims with status `failed` are dropped.
2. The claim with the lowest `ts` wins. `ts` compares as numbers (`ts_key`: `(seconds, microseconds)` as integers).
3. Equal `ts`: the lower `by` string wins.
4. No claim gives `None`.
5. The function does not change its input.

## ThreadState (input of `route`)
Built by the adapter. Frozen.

| Field | Type | Rule |
|---|---|---|
| `channel`, `thread_ts` | str | |
| `starter` | str? | `sender_id` of the parent message (a person, or a bot that posted it, spec 004). `None` when unknown. |
| `parent_text` | str | Text of the parent message. |
| `messages` | tuple[TaskMsg] | Trusted and untrusted task messages in `ts` order. `check_task_msg` filters them. |
| `cards` | dict[agent_id, Card] | From the card cache (key: card `bot_id`). |
| `agent_users` | dict[handle, agent_id] | Card `bot_user_id` of each trusted card to its `bot_id`. Built from the cards, with no transport call. |
| `self_id`, `self_handle` | str | Own `agent_id` and mention handle (`Transport.whoami`). |
| `in_flight` | frozenset[str] | 001 in-flight keys, plus step keys `step:<channel>:<thread_ts>:<i>`. The stepper also uses the keys `start:`, `refuse:`, `approve:`, and `retry:` (same format, with the channel and the `ts`) for the writes that must not run twice. |
| `seen_event_ids` | frozenset[str] | 001 `event_ids`. |
| `flows` | Mapping[str, Flow] | The valid templates of this adapter, by name (spec 006 builds it through `flows_io.py`). Default: empty. `Flow` has `hash: str` and `matches(steps, cards, starter) -> bool` (spec 006). Empty `flows` means every plan has the effective source `free`. |

Derived (pure functions on `ThreadState`): `find_plan` (the earliest trusted plan message that has a `pipeline`, with `by` equal to the planner), `planner` (`first_agent(parent_text, agent_users)`), `step_status`, `thread_status`.

## Events (input of `route`)
| Event | Fields |
|---|---|
| `HumanMessage` | `event_id?`, `channel`, `ts`, `thread_ts`, `sender_id`, `text` |
| `BotMessage` | `event_id?`, `channel`, `ts`, `thread_ts`, `sender_id`, `payload?` (the `pipe.task.v1` payload) |
| `Reaction` | `event_id`, `channel`, `item_ts`, `sender_id`, `name` |
| `Click` | `event_id`, `channel`, `message_ts`, `sender_id`, `action` (`approve` or `retry`; the adapter maps the button `action_id`) |
| `Wake` | `thread_ts`, `now` (adapter start or reconnect, or the dialog timer; one per open thread) |

## Decision (output of `route`)
`Decision(action, reason, arg)`. `action` is one of:

| Action | Meaning | `arg` |
|---|---|---|
| `ignore` | Do nothing. `reason` says why. | |
| `chat` | Plain 001 reply. | |
| `status_query` | 001 status answer. | |
| `plan` | This adapter is the planner. Run the planner. | |
| `start` | Post the start handoff for step 0. | plan message |
| `claim` | Claim and run the step. | handoff message, step index |
| `refuse` | Post `failed`, `reason: hop limit exceeded` (plus ` (plan source not verified)` when a declared template is not verified). | handoff message |
| `approve` | Mark the approval message `done`. | message |
| `retry` | Start a new claim for the failed step. | message, step index |
| `interrupt` | Fail an own `running` step with `reason: interrupted`. | message |
| `plan_flow` | This adapter is the planner and the message has a `flow:<name>` word. Expand the template with no runtime call (spec 006). | flow name |
| `resume` | Run the same step again after a valid dialog answer. No new claim, no `hop` change. | question message, reply message |
| `release` | Release a gate or a proposal: post what the step would have posted without the gate. | type 5 message |
| `expire_dialog` | Fail an own waiting step with `reason: dialog_timeout` and a "Retry" button. | question message |

`route` rules, in order:

1. `HumanMessage`: apply the 001 `should_handle` rules (self, dedupe, mention). A top-level message is a pipeline request when the text names two or more distinct agents with a card (`mentions`, `agent_users`), or when it names one or more such agents and `flow_word(text)` is not `None` (FR-002, FR-044). For a pipeline request: `plan_flow` (arg: the flow name) if there is a `flow:` word and this adapter is the first named agent, `plan` if there is no `flow:` word and this adapter is the first named agent, else `ignore(not_planner)`. A thread reply: if `open_question(thread)` is a question by this adapter, the reply mentions this adapter, and the sender is the thread starter or the card owner of this adapter: `resume`. Any other thread reply with agent mentions is `chat` for each named agent (001). Otherwise `chat` or `status_query` (001 rules).
2. `BotMessage`: `check_task_msg` first (card, payload, `by`). A failed check gives `ignore` with the reason. Then, if `next.agent` is not this adapter and is not `any`: `ignore(not_for_me)`. If `next.agent` is `any`: the plan step must be a tag step, and `matches_tag(own card, tag, access)` must be true, else `ignore(not_eligible)`. If `next.access` is not `read`: `ignore(unsupported_access)`. If `hop` is more than `hop_limit(effective_source(plan, flows, cards, starter))`: `refuse` (the reason text gets the suffix ` (plan source not verified)` when the declared source is a template and the effective source is `free`). If the message is a claim or a handoff for a step with `exclude_agents_of` and `claim_excluded(plan, thread, step, this adapter)` is true: `ignore(excluded)`. If the plan does not assign the `next.payload.step` to this agent (a tag step is assigned to every eligible agent): `ignore(not_assigned)`. If this adapter has a claim for that step after the handoff, or the step key is in flight: `ignore(already_claimed)`. Otherwise `claim`.
3. `Reaction`: `white_check_mark` on a plan message with `status: needs_approval`, by this adapter, with no start message, from the thread starter or the owner of the planner card: `start`. `white_check_mark` on a type 5 message with `status: needs_approval`, by this adapter, with `gate_pending` true, from the thread starter or the owner of the planner card: `release` (arg: the message). A ✅ on the plan message does not release a gate. Any other reaction: `ignore`.
4. `Click`: the message must be by this adapter (a claim, or the type 9 message `no_claimer`). `approve`: message with `access: approve` and `needs_approval`, the clicker is the starter or the card owner of this adapter: `approve`. `retry`: message `failed` (type 4, type 9, or type 10), it is the status message of its step, no type 11 message exists for the step (else `ignore(already_branched)`), same clicker rule: `retry`. For the type 9 message the stepper posts the handoff again (same `hop`) in place of a new claim. After spec 004, a message with `reason: rejected` gives `ignore` (no Retry after a reject). Any other click: `ignore`.
5. `Wake`: each own step whose `step_status` is `claimed` or `running` and whose step key is not in flight: `interrupt`. Each own type 10 message with `status: waiting` and `dialog_expired(ts, now, dialog_timeout_h)`: `expire_dialog`. A waiting question that is not expired gives `ignore` (it is not interrupted). Each open handoff for this adapter with no claim: `claim` (a tag handoff counts when the own card matches the tag). Each plan by this adapter that has an allowed ✅ and no start message: `start`. Each parent message that names this adapter as the planner and has no plan message: `plan`.

## RunRequest
File: `src/pipe/core/runrequest.py`. Frozen dataclass. The only thing that the core gives to a runtime about capabilities and rights. It is also the new field `RuntimeInput.request`.

| Field | Type | Rule |
|---|---|---|
| `capabilities` | tuple[str] | `capability_id` values to load. One for a bot step (the bound ID for a tag step). Empty for the planner call. |
| `access` | enum | `read` or `write`. Never `approve` (an approval step runs no runtime). `write` is refused in 003. |
| `requester_is_owner` | bool | True when the thread starter is the owner of the agent that runs the step. False when `owner` is empty. |
| `output_schema` | dict? | The `output_schema` of the capability, when it has one (copied by the stepper). The adapter passes it to its runtime when the runtime supports it. |

`build_run_request(step, starter, owner, output_schema=None) -> RunRequest`. The step is a bound step (`bind_step`). See research.md D9.

`effective_payload(step_payload, results) -> dict` (`core/runrequest.py`, FR-037). `results` is the list of `{step, text, artifacts}` of the `done` steps before the step, in step order. The result is the plan `payload` plus the keys `context` (the list, `text` cut to `MAX_CONTEXT_TEXT`, all texts cut to `MAX_CONTEXT_TOTAL` from the end) and `artifacts` (all links, in order, no duplicate). A key that the plan `payload` sets wins. When `results` is empty, the function adds no key. The function does not change its input. `check_input` validates this effective payload. The runtime gets it as `task.payload`.

`pick_runtime(caps, capability_id, default) -> str` returns the `runtime` of the capability (`claude`, `exec`, or `http`). It returns `default` (`runtime.name`) for an empty ID (the planner call). It raises `LookupError` for an ID that no local capability has (the stepper turns this into `capability not available`). `check_input(step, cap)` returns `None` or the reason `invalid_payload` (with the error sentences). `check_output(output, cap)` returns `None` or `invalid_result`. Both use `validate_schema` of spec 002. A capability without a schema always gives `None`. The `claude` adapter maps it with `map_request(request, caps, exposed, claude_cfg) -> StepTools(policy: ToolPolicy, load: LoadSet)` (`src/pipe/runtime_claude_request.py`). `ToolPolicy` (defined in `runtime_claude_tools.py`, 001) and `LoadSet` (002) both stay in the `claude` adapter. The core holds neither.

## Metrics
`compute_metrics(threads, mr_states, cards, now) -> Metrics`. Input: the trusted task messages of each thread, with reactions, the starter, and `mr_states: dict[url, {state, merged_at}]`. The states come from `MrStatePort` (a replaceable provider; GitLab is the first). `state` is `open`, `merged`, or `closed`. The core knows no provider term.

| Metric | Definition |
|---|---|
| `delegations_per_week` | Count of steps with an MR URL in `artifacts`, whose agent owner is not the thread starter, and whose MR state is `merged`. Grouped by ISO week of `merged_at`. Output: the count for each week in the window and the average. |
| `clean_pipelines_share` | Among pipelines that were started and are `done` or stopped (`failed` or hop refused): the share that are `done`, have no `failed` step message, and have no human message in the thread after the start message, except the approval clicks (Q8 = a). A click is not a message. A `waiting` step is not manual help. A human answer to a dialog question (a thread reply that `open_question` accepted) is not manual help (default of the second batch, open question U6). A ✅ release is a reaction, not a message. A pipeline in `running`, `waiting`, or `needs_approval` is not counted. `n/a` if the denominator is 0. |
| `noisy_share` | Agent messages (trusted bot messages in the window) that have a `mute` (🔇) reaction, divided by all agent messages. Also `hop_stops`: the number of threads with a `failed` message with `reason: hop limit exceeded`. |
| `owner_offline_wait_median` | Median seconds from the `ts` of a `waiting` message with `reason: owner offline` to the `ts` of the first later claim of the same step. A wait with no later claim is not in the median. The count of open waits is printed. `n/a` if there is no closed wait. |

`render_metrics(metrics, thresholds)` prints one line per metric: the value, the brief §10 threshold, and `ok`, `below`, or `track` (for the median).
