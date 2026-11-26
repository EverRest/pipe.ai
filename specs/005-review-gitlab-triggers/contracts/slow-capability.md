# Contract: Slow capability (review, e2e, long tasks)

Source: design brief §3 decision 8, §6 (Review), §9 (M4). Spec FR-001 to FR-012, FR-024 to FR-026. This contract adds no message type and no status. It uses the messages of [../../003-chat-pipelines/contracts/task-metadata.md](../../003-chat-pipelines/contracts/task-metadata.md) and the runtime output of [../../003-chat-pipelines/contracts/runtime-request.md](../../003-chat-pipelines/contracts/runtime-request.md). It is not review-only: a review, an e2e run, a long test run, and any other long task use it.

## Generic rule: how a slow capability reports completion

1. The claiming adapter posts the claim (type 4, `claimed`, then `running`).
2. The adapter calls the capability through its runtime adapter (`exec` for a declared script). The call returns when the work ends.
3. The adapter keeps the claim `running` while the call runs. The core does not know that the capability is slow.
4. The call ends with success: the adapter posts the result (type 5 `done` with `artifacts` and `next`).
5. The call ends with a runtime result `status: failed`: the step is `failed` with `reason: run_failed`. When the plan step has `on_fail`, the claiming adapter posts one type 11 branch handoff (no button). Else the claim message gets a "Retry" button.
6. The call ends with an error that is not a result (a non-zero exit code, a timeout, bad output): the adapter raises `RuntimeFailed`. The step is `failed` with that scrubbed reason and a "Retry" button. There is NO branch.
7. The call does not end within `step_timeout_min`: the adapter stops the call and posts `failed` with `reason: timeout` and a "Retry" button. No branch.
8. Only a message from the claiming bot counts as a completion. A "done" from any other bot, from a person, or from an external system has no effect.
9. A second `done` or a second handoff for the same step is ignored (`duplicate_handoff`). The next step starts once.

No callback, no new trust path, and no new field in a task message exist.

## Output of a wrapper (one JSON object on stdout)

```json
{ "text": "short summary", "status": "done", "artifacts": ["https://..."], "data": {}, "files": ["/Users/<owner>/.pipe/run/<id>/report.html"] }
```

| Field | Rule |
|---|---|
| `text` | Required. Scrubbed by the adapter. |
| `status` | Optional. `done` (default) or `failed`. |
| `artifacts` | Optional. `https://` links. |
| `data` | Optional. Checked against the `output_schema` of the capability (003 `check_output`). |
| `files` | Optional (open question O1 of plan.md). Absolute paths of files that the wrapper made. |

### The branch rule (`on_fail`)

- A wrapper that wants the `on_fail` branch MUST print `{"status": "failed", "text": "..."}` and MUST exit with code 0.
- A wrapper that exits with a non-zero code gives `RuntimeFailed("exit <code>")`. The step does NOT branch, also when stdout holds `{"status": "failed"}`. The exit code wins.
- Example: an e2e wrapper finds a failed test. It prints `{"status": "failed", "text": "3 tests failed"}` and exits 0. The planner or the template set `on_fail` to a "troubleshoot" step. The branch handoff goes to that step. A wrapper that crashes (exit 1) gives "Retry" and no branch.

### Files (`Transport.upload_file`)

- After a successful or failed result, the adapter (outside the core) uploads each path of `files` with `Transport.upload_file(channel, thread, name, data, title)` and appends each returned link to `artifacts`. The scope is `files:write` (spec 001).
- A path MUST be a regular file inside `~/.pipe/run/`, not a symbolic link, at most 10 MB. Else the transport raises `UploadRefused` and the step is `failed` with `reason: upload refused`. No file is sent.
- `name` and `title` are scrubbed by the transport. The content is not scanned: the wrapper is responsible for its screenshots and reports.
- The core never reads a file and never sees a path. It sees links in `artifacts`.

## Review capability

A review capability is a capability with the tag `review`. The owner sets the tag in the config map `tags`. The card shows the tag. A plan step can name it as `capability: "tag:review"` with `agent: "any"`, or by a fixed agent and a fixed capability ID. The planner and the templates set `exclude_agents_of` on a review step (spec 003 FR-039).

| Item | Rule |
|---|---|
| `access` | `read`. |
| `input_schema` | The effective payload needs a change link: a string `mr_url`, or a non-empty `artifacts` list. A schema with `additionalProperties: false` MUST list `context` and `artifacts`. A payload that fails gives `failed`, `reason: invalid_payload`, and no run. |
| Payload | The step `payload` plus `context` and `artifacts` of ALL earlier done steps (`effective_payload(step_payload, results)`, spec 003). |
| Result | `text` (short summary) and `artifacts` (links to the drafts). |
| Exposure | `owner-only` until the owner exposes it. |

## wiz-review implementation (first implementation, DQ1 = a)

A capability declared in the owner config. Its wrapper is `templates/review/wiz_review_capability.py`.

Input: the effective payload as JSON on stdin. Output: the object above. Exit code 0 is success. Another exit code is a failure, and the scrubbed stderr text is the reason (no branch).

Steps of the wrapper:

1. Find the change link: `mr_url`, else the first `https://` link of `artifacts`. No link gives exit code 2 and the text `missing change link`.
2. Ask the wiz-review state for that change.
3. State `none`: send one review request. State `pending`: send no request. State `ready`: go to step 5.
4. Poll the state every 15 seconds until it is `ready` or `error`. The adapter step time limit stops a wait that does not end.
5. Print the result and exit 0.

Rules:

- One MR gives at most one request, also after a "Retry" (FR-012).
- The wrapper does not change wiz-review and reads no wiz-review secret from a file in this repo.
- The wiz-review commands come from environment variables of the declared capability. No path, URL, or token is in the card or in this repo.
- Option (b) of DQ1 (a callback) and option (c) (an own bot) are not built.
