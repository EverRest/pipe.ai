# Quickstart: Validate Review and Triggers

Use this guide after implementation. It proves the three user stories. It holds no implementation code. Specs 001 to 004 must be installed and working (`pipe doctor` passes, the cards are in `#pipe-agents`, a chat pipeline and a delegation run).

## Prerequisites

- Two adapters: `coder-pavlo` (owner Pavlo) and `reviewer-olena` (owner Olena). Both have a card.
- On the laptop of Olena: wiz-review works. Her config declares the review capability (see `templates/review/config.example.yaml`), tags it `review` in `tags`, and lists it in `exposed`. Her card shows the capability with the tag `review`.
- A Slack app for the trigger bot (example name `pipe-gitlab`) with the scopes `chat:write` and `pins:write`. It needs no event scope. The agent apps need `files:write` for the upload of wrapper files (spec 001). Its token is a masked CI variable (`PIPE_TRIGGER_TOKEN`). Do not write the token in any file.
- A GitLab project with a Pipeline schedule (GitLab UI). The job uses `templates/trigger/gitlab-ci.yml`. The variables are `PIPE_CHANNEL`, `PIPE_AGENT_USER_ID`, `PIPE_PIPELINE_FILE` (a fixed pipeline) or `PIPE_FLOW` (a flow name), and `PIPE_TRIGGER_TITLE`. Use one of `PIPE_PIPELINE_FILE` and `PIPE_FLOW`, never both.
- The trigger bot posted its card once: `python3 templates/trigger/post_trigger.py card` (run by its owner, with the token in the environment).

## 1. Unit and integration tests (no Slack, no LLM, no network)

```text
pytest tests/unit tests/integration
```

Expected: all pass. Covers SC-001 to SC-004 and SC-006 to SC-012 with fakes. The import-boundary test (SC-004) is part of it.

## 2. Scenarios (real Slack)

| Story | Steps | Expected |
|---|---|---|
| 1 | Pavlo writes in `#pipe-work`: "@coder-pavlo fix the typo, then ask a reviewer". The plan has a step with `tag:review`. Pavlo adds ✅. | The plan check passes. After the first step gives an MR link, `reviewer-olena` claims the review step. |
| 1 | Look at the thread while the review runs. | The review step shows `running`. The next step does not start. |
| 1 | Wait for the drafts. | The review step shows `done`. The next step starts. |
| 2 | Repeat with a review that ends late. Post "done" by hand as a person. | The step stays `running`. The message has no effect. |
| 2 | Click "Retry" after a timeout. | wiz-review shows one review request for the MR, not two. |
| 3 | Put the trigger bot ID in the allowlist of `coder-pavlo`. Run the GitLab schedule once. | A mention appears in `#pipe-work`. A plan and a start message follow. No ✅ and no button. |
| 3 | Remove the allowlist entry. Run the schedule again. | The plan shows Accept and Reject. No step starts. |
| 3 | A person other than Pavlo clicks Accept. | Nothing changes. |
| 3 | Pavlo clicks Accept. | The pipeline starts. |
| 3 | Run again. Pavlo clicks Reject. | The plan is `failed`, `rejected`. No "Retry" button. |
| 3 | Use a plan file with an unknown agent. | The thread shows the plan errors. No button. |
| 3 | Set `PIPE_FLOW` to a flow name (and no plan file) with a goal in `PIPE_TRIGGER_TITLE`. | The plan comes from the template with no LLM call. The same gate applies. |
| 3 | Set both `PIPE_FLOW` and `PIPE_PIPELINE_FILE`, or neither. | The mention has no effect (`bad_payload`). |
| 2 | Use an e2e wrapper that prints `{"status": "failed"}` and exits 0, with `on_fail` set. | The branch handoff (type 11) starts the troubleshoot step. A wrapper that exits 1 gives "Retry" and no branch. |
| 2 | Use a wrapper that lists a screenshot in `files`. | The thread shows the uploaded file link in `artifacts`. A path outside `~/.pipe/run/` gives `upload refused`. |
| 3 | Use a plan file that names the trigger bot as a step agent. | The plan is rejected. |
| 3 | Stop the adapter of `coder-pavlo`. Run the schedule. Start the adapter. | The adapter takes the mention at start. |
| 3 | Add `coder-pavlo` to its own allowlist, and use a `write` step for it. | The step starts without a button (DQ5 = a). Without the entry, the owner gets a button. |

SC-005: measure the time from the schedule start to the first step message. It must be under 2 minutes.

## 3. Checks on real systems

- The wiz-review request and state commands match the wrapper (T031).
- Slack delivers the trigger mention to the mentioned adapter (T032).
- The GitLab job reads the masked variable and reaches Slack (T033).
- No file in the repository holds a token (T030).
