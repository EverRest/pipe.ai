# Contract: Tag vocabulary

Source: owner decision 3 for spec 006. Spec FR-012 to FR-014. The file is `flows/tags.yaml`. It is data. The core receives it as an argument. No core module holds a tag name (principle XI).

## File format

```yaml
version: 1
tags:
  decompose:
    access: read
    meaning: "Break a request into tasks. Returns a task proposal."
  implement:
    access: write
    meaning: "Change code in a worktree. Result is an MR."
```

Rules (`validate_tags(data) -> list[str]`):

1. `version` is 1.
2. Each tag key matches `^[a-z0-9-]{1,32}$`.
3. `access` is `read` or `write`. (`approve` is for human steps and has no tag.)
4. `meaning` has 1 to 120 characters.

## Standard tags (version 1)

| Tag | Default access | Meaning |
|---|---|---|
| `decompose` | read | Break a request into tasks. Return a task proposal. |
| `implement` | write | Change code in a separate worktree. The result is an MR. |
| `e2e` | read | Run end-to-end tests on a branch or an environment. Return a report and screenshots. |
| `review` | read | Review a change (an MR). Return drafts or comments. |
| `reproduce` | read | Make a failing test that shows a bug. |
| `brainstorm` | read | Discuss an idea with the people in the thread (a dialog). |
| `context` | read | Collect context from repos, docs, and MRs. |
| `research` | read | Search the web, docs, and code for an answer. |
| `summarize` | read | Make a summary or a document from earlier results. |
| `spec` | write | Write a spec document or an MR with a spec. |
| `collect` | read | Collect logs, metrics, or cluster state. |
| `diagnose` | read | Find the cause of a fault from collected data. |
| `troubleshoot` | read | Check a failed result and say what to do. |
| `deps-check` | read | Check dependencies for outdated or unsafe versions. |

## How an owner gives a tag

The owner maps capability IDs to tags in `~/.pipe/config.yaml` (spec 002):

```yaml
tags:
  claude:skill:superpowers:brainstorming: [brainstorm]
  exec:run-playwright: [e2e]
```

The card then shows the tag. A capability that is `owner-only` is not in the card, so it does not count (principle III).

Declared capabilities (`exec`, `http`) are `read` only (spec 002). They can carry the tags with default access `read` (for example `e2e`, `collect`, `deps-check`). The tags `implement` and `spec` (default `write`) need a capability of the `claude` runtime adapter, because only that adapter runs a worktree (spec 004).

## Missing tags

`missing_tags(flow, params, cards) -> list[str]` returns the tags of the flow that no trusted card offers. `expand_flow` turns the list into one error with all names (spec FR-011). `pipe flows` prints the same list for each template.

## Changes to the vocabulary

A new tag is a merge request that changes `flows/tags.yaml`. A template that uses an unknown tag is invalid. The default access of a tag does not change without a review: a change from `read` to `write` changes the risk of every template that uses the tag.
