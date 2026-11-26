# Contract: Owner gate

Source: design brief §5.4, §6 (flow C), §8, decision 4. Spec FR-004 to FR-009. Extends [../../003-chat-pipelines/contracts/task-metadata.md](../../003-chat-pipelines/contracts/task-metadata.md). Spec 003 is not changed by this file. Fields are in [../data-model.md](../data-model.md).

## Names

The owner gate is a type 4 message (the claim) with `status: needs_approval` and the buttons `pipe_accept` and `pipe_reject`. It is not the type 5 `needs_approval` of spec 003 (the `gate: approval` step field or a plan proposal, released by ✅ that posts a NEW type 5 `done`). Type 10 is the dialog question. Type 11 is the branch handoff. This contract changes none of them.

## When the gate runs

1. The adapter gets a valid handoff for a step (003 `route` gives `claim`). The `next.access` is `read` or `write`.
2. The adapter posts the claim (type 4, `claimed`) and resolves duplicate claims (003 contest).
3. The winner calls `decide_gate(access, starter, executor_owner, sender, sender_owner, allowlist)`. `starter` is the `sender_id` of the poster of the parent message (a person id, or a bot id). For a tag step (spec 003), the winner of the claim runs these steps, with its own owner and allowlist. The loser shows no button. The payload check of spec 003 runs before step 3.
4. `allow` needs one of two cases: the owner of the receiving agent started the thread; or the sender is in the allowlist and the thread starter is the owner of the sender or is in the allowlist (DQ2). The claim goes to `running`. The run starts (003 `run_step`).
5. `ask`: the claim goes to `needs_approval` with two buttons. No runtime runs. No worktree exists.

The thread starter can be a bot ID. An allowlisted trigger bot (spec 005) is a trusted starter. An unknown starter gives `ask`.

A `read` step always gives `allow` (reason `not_write`, DQ1). The owner should set `max_budget_usd` (001).

## Allowlist shape (shared with spec 005)

```yaml
allowlist: [B012ABCDEF, U034GHIJKL]   # sender ids (Slack: bot IDs and user IDs)
```

- Each entry matches `Transport.id_pattern` (Slack: `^[BUW][A-Z0-9]{2,}$`). A bad entry makes the config load fail with a clear error.
- `in_allowlist(allowlist, subject)` is an exact match on the string. The core does not read the kind of ID.
- Delegation checks two IDs: the handoff sender (a bot ID) and the thread starter (a user ID, or a bot ID when a bot started the thread). Both must pass (decision table in the data model, DQ2).
- Spec 005 checks the `bot_id` of a `kind: trigger` bot with the same function.
- Only the owner edits the file. The adapter never writes the allowlist. A button never adds an entry.

## Message (type 4, gate state)

`metadata.event_payload`: `phase: step`, `access: write`, `status: needs_approval`, `by: <id of the receiving agent>`, `step`, `hop` (as received). No new field.

Block Kit `actions` block:

| `action_id` | Label | Effect | Who may click |
|---|---|---|---|
| `pipe_accept` | Accept | The claim goes to `running`. The run starts. The buttons are removed. | The card `owner` of the receiving agent only. |
| `pipe_reject` | Reject | The claim goes to `failed` with `reason: rejected`. The buttons are removed. No run. | The card `owner` of the receiving agent only. |

A click from another person, the thread starter too, changes nothing and posts nothing. The adapter logs it. A second click, or a click on a message that is not in the state `needs_approval`, changes nothing.

## Texts (`render_task`)

```text
Step 2 of 3 (write, coder-bob): needs approval. <@U_OWNER> Accept or reject this work from coder-pavlo.
Step 2 of 3 (write, coder-bob): running
Step 2 of 3 (write, coder-bob): failed. Reason: rejected
```

The goal is not in the gate text. It is in the plan message. The mention of the owner is a real `<@U...>`. Every other mention is escaped (003 rule). No text holds a path, a token, or a URL, except the MR link in `artifacts`.

## State after a restart

`Wake` (003) does not `interrupt` a claim in the state `needs_approval`. The buttons stay valid. A click after the restart works once.

## Rules

1. The gate runs after the claim contest, so one bot gives one button.
2. The gate adds no `hop`.
3. A `needs_approval` claim is a live claim. The owner-offline timer of the sender does not post `waiting` for it.
4. A rejected step is final. It has no "Retry" button (DQ7). The thread starter writes a new request. A rejected `write` tag step gets no second claimer, also after a restart (`step_rejected`, spec 003 FR-046).
5. The step has no expiry in 004 (DQ5).
