# Contract: Flow catalog version 1 (template files)

Source: owner flow catalog for spec 006. Spec FR-029. Each block below is the exact content of one file in `flows/`. The format is in [flow-template.md](flow-template.md). The tags are in [tag-vocabulary.md](tag-vocabulary.md). The tasks create the files from this document. A template file has no agent name, no plugin, no tool, no URL, and no path.

Status sync (flow B) is not a flow. It runs from hooks (spec 001). It has no file here.

## Summary table

| File | Agent steps | Human step | On fail | Gates in the file | Trigger |
|---|---|---|---|---|---|
| `feature-dev.yaml` | 4 | yes | no | `decompose` has `gate: approval` | chat |
| `bugfix.yaml` | 4 | yes | no | none | chat, issue |
| `planning.yaml` | 3 | no | no | `decompose` has `gate: approval` | chat |
| `brainstorm.yaml` | 3 | no | no | none | chat |
| `research.yaml` | 2 | no | no | none | chat |
| `test-run.yaml` | 2 | no | `e2e` to `troubleshoot` | none | chat, schedule, MR |
| `troubleshoot.yaml` | 3 | yes | no | none | alert, chat |
| `review-handoff.yaml` | 3 | yes | no | none | MR, chat |
| `delegate.yaml` | 1 | no | no | none | chat |
| `nightly.yaml` | 2 | no | `check` to `troubleshoot` | none | CI schedule |

The 004 gate and the trigger gate are not in the files. They come from the access of each step and from the thread starter.

## feature-dev.yaml

```yaml
name: feature-dev
version: 1
description: "Build a feature: decompose, implement, test, review, approve."
steps:
  - id: decompose
    agent: any
    capability: "tag:decompose"
    goal: "Break this request into tasks and propose them: {goal}"
    gate: approval
  - id: implement
    agent: any
    capability: "tag:implement"
    goal: "Implement the approved tasks in a branch and open an MR: {goal}"
  - id: e2e
    agent: any
    capability: "tag:e2e"
    goal: "Run the end-to-end tests on the branch. Attach the report and screenshots."
  - id: review
    agent: any
    capability: "tag:review"
    goal: "Review the MR."
    exclude_agents_of: [implement]
  - id: approve
    agent: "$starter"
    access: approve
    goal: "Approve the result."
```

## bugfix.yaml

```yaml
name: bugfix
version: 1
description: "Fix a bug. A failing test comes first."
steps:
  - id: reproduce
    agent: any
    capability: "tag:reproduce"
    goal: "Reply with a failing test for this bug: target file path, test code, expected failure. Bug: {goal}"
  - id: implement
    agent: any
    capability: "tag:implement"
    goal: "Add the failing test from the reproduce reply. Fix the bug so that the test passes. Open an MR: {goal}"
  - id: e2e
    agent: any
    capability: "tag:e2e"
    goal: "Run the end-to-end tests on the branch. Attach the report."
  - id: review
    agent: any
    capability: "tag:review"
    goal: "Review the MR."
    exclude_agents_of: [implement]
  - id: approve
    agent: "$starter"
    access: approve
    goal: "Approve the result."
```

## planning.yaml

```yaml
name: planning
version: 1
description: "Turn an idea into a spec and a task proposal."
steps:
  - id: brainstorm
    agent: any
    capability: "tag:brainstorm"
    goal: "Discuss this idea with the people in the thread. Ask questions when you need input: {goal}"
  - id: spec
    agent: any
    capability: "tag:spec"
    goal: "Write a spec from the discussion. Open an MR or make a document: {goal}"
  - id: decompose
    agent: any
    capability: "tag:decompose"
    goal: "Break the spec into tasks and propose them."
    gate: approval
```

## brainstorm.yaml

```yaml
name: brainstorm
version: 1
description: "Discuss a topic with context from repos, docs, and MRs. Keep a summary."
steps:
  - id: context
    agent: any
    capability: "tag:context"
    goal: "Collect context for this topic: {goal}"
  - id: brainstorm
    agent: any
    capability: "tag:brainstorm"
    goal: "Discuss this topic with the people in the thread: {goal}"
  - id: summary
    agent: any
    capability: "tag:summarize"
    goal: "Write a summary of the discussion as a document."
```

## research.yaml

```yaml
name: research
version: 1
description: "Research a question in the web, docs, and code. Keep a document."
steps:
  - id: research
    agent: any
    capability: "tag:research"
    goal: "Research this question: {goal}"
  - id: summary
    agent: any
    capability: "tag:summarize"
    goal: "Write a document with the findings and the source links."
```

## test-run.yaml

```yaml
name: test-run
version: 1
description: "Run the end-to-end tests. On failure, troubleshoot."
steps:
  - id: e2e
    agent: any
    capability: "tag:e2e"
    goal: "Run the end-to-end tests: {goal}. Attach the report and screenshots."
    on_fail: troubleshoot
  - id: troubleshoot
    agent: any
    capability: "tag:troubleshoot"
    goal: "Find the cause of the test failure and say what to do."
```

## troubleshoot.yaml

```yaml
name: troubleshoot
version: 1
description: "Find the cause of a fault and propose a fix."
steps:
  - id: collect
    agent: any
    capability: "tag:collect"
    goal: "Collect logs, metrics, and cluster state for this fault: {goal}"
  - id: diagnose
    agent: any
    capability: "tag:diagnose"
    goal: "Find the cause of the fault from the collected data."
  - id: implement
    agent: any
    capability: "tag:implement"
    goal: "Fix the cause in a branch and open an MR."
  - id: approve
    agent: "$starter"
    access: approve
    goal: "Approve the fix."
```

## review-handoff.yaml

```yaml
name: review-handoff
version: 1
description: "Review a change, fix the comments, review again."
steps:
  - id: review
    agent: any
    capability: "tag:review"
    goal: "Review this change: {goal}"
  - id: implement
    agent: any
    capability: "tag:implement"
    goal: "Fix the review comments. Update the MR."
  - id: re-review
    agent: any
    capability: "tag:review"
    goal: "Review the fixes."
    exclude_agents_of: [implement]
  - id: approve
    agent: "$starter"
    access: approve
    goal: "Approve the result."
```

## delegate.yaml

```yaml
name: delegate
version: 1
description: "Ask the agent of another owner to change a repo of that owner."
steps:
  - id: implement
    agent: "$agent"
    capability: "tag:implement"
    goal: "Make this change in your repo and open an MR: {goal}"
```

## nightly.yaml

```yaml
name: nightly
version: 1
description: "Run a regular check from a schedule. On failure, troubleshoot."
params:
  check:
    values: [e2e, deps-check]
    default: e2e
steps:
  - id: check
    agent: any
    capability: "tag:$check"
    goal: "Run the check {check} and write a report: {goal}"
    on_fail: troubleshoot
  - id: troubleshoot
    agent: any
    capability: "tag:troubleshoot"
    goal: "Find the cause of the failed check and say what to do."
```

## Checks that the catalog must pass

1. Each file passes `validate_flow` with the vocabulary.
2. Each file expands with fake cards that offer all its tags, and the result passes `validate_plan` (003 and 004 rules).
3. The expanded plan has `source: template:<name>@<hash>`, and `effective_source` gives `template`.
4. The count of agent steps is at most 5 in each file.
5. Removing one tag card gives the error `flow <name>: missing tags: <tag>`.
6. The directory has these ten files and `tags.yaml`, and no other file.
