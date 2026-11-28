# Flows

Each diagram follows the code. Nobody tested these flows with live services.

## Mention and reply

```mermaid
sequenceDiagram
    actor P as Person
    participant S as Slack
    participant A as Adapter
    participant R as claude -p
    P->>S: Mention the agent in a thread
    S->>A: app_mention
    A->>S: Read the thread
    A->>R: Thread as untrusted data
    Note over A,R: Tools only if the sender is the owner and all messages are from the owner or this agent
    R-->>A: text and status
    A->>S: Reply in the thread (scrubbed, mentions escaped)
```

A mention with the words `who works on what` gives a summary from the status channel. It does not call `claude`.

## Pipeline: plan and check mark

A top-level message starts a plan when it mentions two or more agents, or one agent and `flow:<name>`.
The first mentioned agent is the planner.

```mermaid
sequenceDiagram
    actor P as Starter
    participant S as Slack work channel
    participant A as Planner adapter
    participant B as Step adapter
    P->>S: Mention agents A and B with a goal
    S->>A: app_mention
    A->>A: Build the plan (claude with no tools, or a flow template)
    A->>A: Check the plan
    A->>S: Post the plan (needs_approval)
    P->>S: Add the white_check_mark reaction
    S->>A: reaction_added
    A->>S: Handoff for step 1 with a mention
    S->>B: app_mention, or the wake pass
    B->>S: Post a claim
    B->>B: Wait 2 s, the lowest message timestamp wins
    B->>S: running, then done
    B->>S: Result and handoff for the next step
```

- Only the thread starter or the owner of the planner agent can release a plan.
- The adapter runs a wake pass each 60 seconds on threads of the last 7 days. It finds handoffs and reactions that an event did not deliver.
- A step with `gate: approval` posts its result and waits for the check mark.
- A human `approve` step shows an Approve button.
- A free plan allows `hop` 3 or less. A verified template allows `hop` 5 or less.

## Delegation: owner gate and worktree to MR

```mermaid
sequenceDiagram
    actor O as Agent owner
    participant S as Slack
    participant A as Adapter
    participant R as claude -p
    participant G as git and GitLab
    S->>A: Handoff for a write step
    A->>S: Claim the step
    alt Owner thread, or allowlist rule passes
        A->>A: Start with no button
    else Other cases
        A->>S: Accept and Reject buttons
        O->>S: Click Accept
        S->>A: Click event
    end
    A->>G: git fetch origin base
    A->>G: git worktree add, branch pipe/...
    A->>R: Run in the worktree with write tools
    R-->>A: Result
    A->>G: Commit, push the branch with merge_request.create
    G-->>A: MR link in the push output
    A->>G: Remove the worktree
    A->>S: done with the MR link
```

The button is skipped in two cases:

1. The owner started the thread, and every other message in it is from the owner or this agent.
2. The sender agent is in `allowlist`, the starter is the owner of the sender agent or is in `allowlist`, and every other sender in the thread is the owner or is in `allowlist`.

The adapter makes the commit and the push. The model does not. A human merges the MR.

## Trigger from CI

```mermaid
sequenceDiagram
    participant CI as CI job
    participant S as Slack work channel
    participant A as Adapter
    actor O as Agent owner
    CI->>S: post_trigger.py posts a mention with pipe.task.v1 metadata
    S->>A: app_mention
    A->>A: Check the trigger card, then build and check the plan (no LLM)
    alt Trigger bot ID is in allowlist
        A->>S: Post the plan and start step 1
    else Not in allowlist
        A->>S: Post the plan with Accept and Reject
        O->>S: Click Accept
        S->>A: Click event
        A->>S: Start step 1
    end
```

A trigger needs a trigger card in the agents channel. See [Slack setup](setup-slack.md).

## Review step

A review is a capability with the tag `review`. The example is a declared `exec` capability.
**The shipped wrapper has a defect** (see [Known defects](../../README.md#known-defects)). The diagram shows the intended path.

```mermaid
sequenceDiagram
    participant S as Slack
    participant A as Reviewer adapter
    participant E as exec runtime
    participant W as Review wrapper
    participant V as Review service
    S->>A: Handoff for a tag review step
    A->>S: Claim, then running
    A->>A: Bind the lowest exposed capability ID with the tag
    A->>E: Payload with context and artifacts
    E->>W: JSON on stdin
    W->>V: Request the review
    loop Each 15 s until ready, error, or timeout
        W->>V: Read the state
    end
    W-->>E: JSON on stdout
    E-->>A: Result
    A->>S: done or failed
```

## Dialog question

```mermaid
sequenceDiagram
    actor P as Starter or agent owner
    participant S as Slack
    participant A as Adapter
    participant R as Runtime
    A->>R: Run the step
    R-->>A: status waiting, reason needs_input
    A->>S: Post the question
    alt Answer in time
        P->>S: Reply in the thread and mention the agent
        S->>A: app_mention
        A->>R: Run the same step again with the thread
        R-->>A: Result
        A->>S: Post the result
    else No answer in 24 h
        A->>S: failed, dialog_timeout
    end
```

A `write` step cannot ask a question. A non-`done` result fails it with `delegate run failed`.

## Flow catalog

The templates are in [flows/](../../flows/). The tag vocabulary is [flows/tags.yaml](../../flows/tags.yaml).

| Flow | Steps (tag) | Access of tags | Notes |
|---|---|---|---|
| `brainstorm` | context (`context`), brainstorm (`brainstorm`), summary (`summarize`) | read | |
| `bugfix` | reproduce (`reproduce`), implement (`implement`), e2e (`e2e`), review (`review`), approve (human) | `implement` is write | `reproduce` returns the test code in its reply. `implement` adds this test to the code. Review excludes the implement agent. |
| `delegate` | implement (`implement`, named agent) | write | Needs a second agent mention. |
| `feature-dev` | decompose (`decompose`, gate), implement (`implement`), e2e (`e2e`), review (`review`), approve (human) | `implement` is write | Review excludes the implement agent. |
| `nightly` | check (`$check`), troubleshoot (`troubleshoot`) | read | Parameter `check`: `e2e` (default) or `deps-check`. `on_fail` goes to troubleshoot. |
| `planning` | brainstorm (`brainstorm`), spec (`spec`), decompose (`decompose`, gate) | `spec` is write | |
| `research` | research (`research`), summary (`summarize`) | read | |
| `review-handoff` | review (`review`), implement (`implement`), re-review (`review`), approve (human) | `implement` is write | Re-review excludes the implement agent. |
| `test-run` | e2e (`e2e`), troubleshoot (`troubleshoot`) | read | `on_fail` goes to troubleshoot. |
| `troubleshoot` | collect (`collect`), diagnose (`diagnose`), implement (`implement`), approve (human) | `implement` is write | |

For `review-handoff`, name the branch in your request, for example `pipe/1700000000-000100-s1`. Then `implement` adds to that MR. You must own the implementing agent and start the thread. Without a branch name, `implement` opens a new MR from the base branch.

Start a flow with a top-level message: `@<agent> flow:<name> [key=value ...] <goal>`.
Each tag of the flow needs an agent card that offers it.
