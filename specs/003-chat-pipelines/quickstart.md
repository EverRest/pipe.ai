# Quickstart: Validate Pipelines from Chat

Use this guide after implementation. It proves the user stories 1 to 12. It holds no implementation code. Specs 001 and 002 must be installed and working (`pipe doctor` passes, the card is in `#pipe-agents`).

## Prerequisites

- Two agents with two adapters (two Slack apps, two Keychain items), for example `coder-pavlo` and `reviewer-olena`. Each has a card in `#pipe-agents`. Each exposes at least one capability (002).
- A channel `#pipe-work`. Both bots are members.
- Slack app changes from [contracts/cli.md](contracts/cli.md): scope `reactions:read` (no `users:read`), event `reaction_added`, Interactivity on. Reinstall both apps. Each card in `#pipe-agents` must hold `bot_user_id` (spec 002).
- Config: `work_channel` (default `pipe-work`). The section `runtime.claude` (`owner_tools`, `repo_roots`, `deny_rules`) has defaults. Set `max_budget_usd` (001): a step that another person starts spends your budget. For `pipe metrics` also the section `mr_state` ([contracts/cli.md](contracts/cli.md)).
- `claude` on `PATH`.

## 1. Unit and integration tests (no Slack, no LLM)

```text
pytest tests/unit tests/integration
```

Expected: all pass. Covers SC-001 to SC-005, SC-008 to SC-012, and FR-001 to FR-027 with fakes. The import-boundary test (SC-011) is part of it.

## 2. Scenarios (real Slack)

| Story | Steps | Expected |
|---|---|---|
| 1 | In `#pipe-work`, write: "@coder-pavlo add a note to the README, then @reviewer-olena reviews it". | `coder-pavlo` posts a plan with `needs_approval`. No step runs. |
| 1 | Add ✅ as a person who is not the thread starter and not the owner of `coder-pavlo`. | Nothing starts. |
| 1 | Write a request that names an agent that has no card (a bot that is not in `#pipe-agents`). | One plan message with the errors. A ✅ on it starts nothing. |
| 1 | Ask for a capability that the card does not list (a hidden capability). | The plan is rejected with an error for that step. |
| 1 | Ask for a step that changes files (access `write`). | The plan is rejected: not supported before spec 004. |
| 1 | Check the Slack scopes of the apps. Read the handoff message. | No `users:read`. The handoff mentions the next agent as `<@bot_user_id>` from its card. |
| 1 | Add ✅ as the thread starter. | A start message mentions the agent of step 1. |
| 2 | Watch the thread. | Step 1: `claimed`, `running`, `done`. Then step 2 starts only after step 1 is `done`. Each state shows in the thread (SC-007). |
| 2 | Use a plan whose last step is a human approval. Click "Approve" as the thread starter. | The approval message goes to `done`. The thread is `done`. |
| 2 | Click "Approve" as a person who is not allowed. | Nothing changes. |
| 3 | Post a message with `pipe.task.v1` metadata from a bot that has no card (use a test app). | No adapter acts. |
| 3 | Ask for a plan with 4 bot steps. | The plan is rejected (too many agent steps). |
| 3 | Post a handoff with `hop` 4 from a test card bot. | The adapter posts `failed`, `hop limit exceeded`. No work runs. |
| 4 | Run two adapters with the same bot token. Start a pipeline. | Two claims appear. The claim with the lowest `ts` stays. The other claim is deleted. The step runs once. |
| 5 | Set `step_timeout_min: 1`. Use a capability that sleeps for 5 minutes. | The step is `failed`, `timeout`, with a "Retry" button, less than 1 minute after the limit. No second run starts alone. |
| 5 | Click "Retry" as the thread starter. | A new claim and a new run for the same step. |
| 5 | Stop the adapter of step 2 before the handoff. Wait 70 seconds. Start it again. | The thread shows `waiting`, `owner offline`. After the start, the step runs. |
| 5 | Kill the adapter while a step is `running`. Start it again. | The step is `failed`, `interrupted`, with a "Retry" button. |
| 2 (FR-019) | Stop an adapter. Approve a plan whose step 1 is for that agent. Start the adapter. | The step runs once. |
| 2 (FR-022) | Start a pipeline as a person who is not the owner of the step agent. Ask the step to use an `owner-only` tool or to read a file. | The tool is denied. The step has the exposed capability only and no file tool. |
| 2 (review) | Use a plan whose step 2 names a capability with the tag `review` (any agent that has one). | The step runs like any other step. It ends when its agent posts `status: done`. |
| 7 | Write: "@coder-pavlo add a note to the README, then any agent that can review it". Check the plan. | The plan has a step `any agent with tag review`. The planner rejects the plan when no card offers the tag. |
| 7 | Approve the plan. Both `reviewer-olena` and a second agent have an exposed capability with the tag `review`. | The handoff mentions both agents. Two claims may appear. The claim with the lowest `ts` stays. The step runs once. |
| 7 | Stop all adapters that offer the tag. Approve the plan. Wait for the step time limit (use `step_timeout_min: 1`). | The sender posts `failed`, `no_claimer`, with a "Retry" button. No step runs. After you start an adapter, "Retry" posts the handoff again and the step runs. |
| 8 | Declare an `exec` capability with an `input_schema` (spec 002), expose it, and write a plan with a step that has a good `payload`. | The `exec` adapter runs the command. The step ends `done`. |
| 8 | Change the `payload` so that it breaks the schema. | The step is `failed`, `invalid_payload`. The command did not run. |
| 8 | Add an `output_schema`. Make the command return a bad `data`. | The step is `failed`, `invalid_result`. |
| 8 | Remove the capability ID from `exposed`. Start a step as a person who is not the owner. | The step is `failed`, `capability not available`. The command did not run. |
| 9 | Use a capability that returns `waiting` with `needs_input` (a question). | The thread shows `waiting for input` and the question. It mentions you. No handoff goes out. |
| 9 | Answer in the thread and mention the agent, as the thread starter. | The same step runs again on the same agent. No second claim. `hop` of the next messages is unchanged. |
| 9 | Answer as another person. | The step stays `waiting`. |
| 9 | Set `dialog_timeout_h: 1`. Do not answer for 70 minutes. | The step is `failed`, `dialog_timeout`, with a "Retry" button. |
| 10 | Use a plan whose step 1 has `gate: approval`. | After step 1, the thread shows `needs approval`. Step 2 does not start. |
| 10 | Add ✅ on that message as the thread starter. | Step 2 starts once. A ✅ on the plan message does nothing. |
| 10 | Use a capability that returns a proposed plan. | The thread shows the proposal and `needs approval`. No step starts. After ✅ the pipeline goes on with its own steps. |
| 10 | Read the payload that step 3 gets. | It has `context` and `artifacts` of steps 1 and 2. |
| 11 | Use a plan whose step 2 excludes step 1. Let the same agent offer the tag of both steps. | The agent that did step 1 does not claim step 2. Another agent does. With no other agent, the step ends `no_claimer`. |
| 11 | Use a plan with `on_fail`. Make step 1 return `status: failed`. | One branch message appears. The branch step runs once. The thread ends after it. |
| 11 | Make step 1 time out. | `failed`, `timeout`, "Retry". No branch. |
| 12 | Write `@coder-pavlo flow:bugfix the login page returns 500` (one agent). | The agent posts a plan from the template with no LLM run (spec 006 needed). |
| 12 | Send a handoff of a free plan with `hop` 4. Send a handoff of a verified template plan with `hop` 4. | The first is refused. The second is accepted. Change one byte of the local template and repeat: the second is refused with `plan source not verified`. |
| 6 | Run `pipe metrics` after several pipelines. | Four lines with the values. Compare them with the thread contents by hand. |

## 3. Metrics check on a known channel (SC-010)

Use a test channel with the known threads that the integration test builds (`tests/integration/test_metrics_cli.py` shows the table). Post the same threads by hand with a test card bot. Run `pipe metrics`. The values must equal the table of the test.

## 4. Manual checks with real `claude` (research.md A3, A7)

1. Run a `read` step as a person who is not the owner. Expected: `claude` shows no `Read`, `Grep`, `Glob`, or `Bash` tool. The exposed capability runs.
2. Ask a step to run `git push`. Expected: the call is denied (checks the always-present deny rule `Bash(git push:*)`).
3. Check that `ls ~/.pipe/run` is empty after each step run, also after a timeout.
