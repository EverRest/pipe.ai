# Contract: Run request (core to runtime adapter)

Source: design brief §5.1 and §5.4, constitution principle XI. Extends [../../001-adapter-core-status/contracts/runtime-contract.md](../../001-adapter-core-status/contracts/runtime-contract.md) by one optional input field. Spec 001 is not changed. Decision record: [../research.md](../research.md) D9, D19, D21.

## What the core gives

```python
# src/pipe/core/runrequest.py  (pure; the core names no tool and no flag)
@dataclass(frozen=True)
class RunRequest:
    capabilities: tuple[str, ...]   # capability_id values from the agent card; empty for the planner
    access: Literal["read", "write"]  # never "approve"; "write" is refused in 003 alone, accepted after spec 004
    requester_is_owner: bool        # thread starter == owner of the agent that runs the step
    output_schema: dict | None = None   # the output_schema of the capability, when it has one (opaque to the core)

def build_run_request(step: Step, starter: str | None, owner: str | None, output_schema: dict | None = None) -> RunRequest: ...
def pick_runtime(caps: list[Capability], capability_id: str, default: str) -> str: ...   # "claude" | "exec" | "http"
```

`RuntimeInput` gets one new optional field: `request: RunRequest | None`. A call with `request = None` follows the 001 contract (the 001 chat path with `tools`). The runtime does not know `hop`, trust, or Slack. It receives no card, no plan, and no Slack ID.

## Which runtime adapter runs

The core picks the adapter with `pick_runtime`. It reads the `runtime` of the local `Capability` for the ID in `request.capabilities`. An empty list (the planner call) gives the default `runtime.name`. The selector `runtime_select.py` (outside the core) calls the adapter that the function names. An ID that no local capability has fails the step with `reason: capability not available`.

| `runtime` | Adapter | Input |
|---|---|---|
| `claude` | `runtime_claude.py` (below) | `request` mapped to flags |
| `exec` | `runtime_exec.py` | JSON on stdin ([../../001-adapter-core-status/contracts/runtime-exec-http.md](../../001-adapter-core-status/contracts/runtime-exec-http.md)) |
| `http` | `runtime_http.py` | JSON in a POST body (same contract) |

`output_schema`: the `claude` adapter merges it as the schema of the property `data` into `--json-schema`. The `exec` and `http` adapters put it in the input. The core validates `data` after the run.

## What the `claude` runtime adapter does

Each runtime adapter owns the mapping from `RunRequest` to its own flags or input. The first adapter is `claude`.

```python
# src/pipe/runtime_claude_request.py  (pure; part of the `claude` adapter)
def map_request(request: RunRequest, caps: list[ClaudeCapability], exposed: list[str], claude_cfg: ClaudeCfg) -> StepTools: ...
```

| Input | `claude` adapter result |
|---|---|
| `capabilities` | `load_set(caps, exposed, capabilities)` (002). One ID, the capability of the step (confirmed decision). It loads exposed items only. `--plugin-dir`, `--allowedTools "Skill(pipe-exposed:<name>)"`, `--mcp-config`, `--strict-mcp-config`. |
| `requester_is_owner` true | `--tools` = `runtime.claude.owner_tools` (default `Read`, `Grep`, `Glob`), with path rules from `runtime.claude.repo_roots`. |
| `requester_is_owner` false | `--tools ""` plus `Skill` when a skill or command loads. No file tool. |
| `access: read` | The tools `Edit`, `Write`, and `NotebookEdit` are removed from `--tools` and added to `--disallowedTools`. |
| `access: write` | Refused in 003 alone: `RuntimeFailed`. Spec 004 defines it (worktree, write tools, [../../004-delegation/contracts/delegation-run.md](../../004-delegation/contracts/delegation-run.md)). |
| every request | `--restricted`, `--permission-mode dontAsk`, and every entry of the effective deny list (`effective_deny_rules`: `Bash(git push:*)` always, plus `runtime.claude.deny_rules`, spec 001 FR-019) in `--disallowedTools`. `mcp__<server>` and `Skill(<name>)` of each `owner-only` item are also denied. |

The adapter makes the files of the load (`prepare`) before the run and removes them (`cleanup`) in a `finally`.

## Runtime output (what the core does with it)

The runtime output is `{text, status, next?, artifacts?, data?, reason?, proposal?}` (spec 001 contract). The stepper acts on it in this order (spec 003 FR-036 to FR-040).

| Output | Core action |
|---|---|
| `status: waiting`, `reason: needs_input` | Dialog: post a type 10 message with `text` as the question. No `next`. The run ends. The step timer stops. |
| `status: done`, `proposal` set | Check `proposal` with `validate_plan` (free plan). Valid: gate (type 5 `needs_approval` with the `pipeline`). Invalid: `failed`, `reason: invalid_proposal`. |
| `status: done`, the step has `gate: approval` | Gate: type 5 `needs_approval`. |
| `status: done` | Normal result (type 5 `done` or type 6). |
| `status: failed` | The step is `failed` with `reason: run_failed`. When the plan step has `on_fail`: post one type 11 message (branch). Else the claim message gets the "Retry" button. |
| `RuntimeFailed(reason)` (timeout, exit code, http code, bad output, `capability not available`) | `failed` with that reason and a "Retry" button. No branch. |
| any other status (`needs_approval`, `delegate`, `waiting` with another reason) | `failed`, `reason: runtime status <s>`, "Retry" button. No branch. |

An `exec` or `http` capability that wants the branch must return `status: failed` in its JSON. A non-zero exit code is `RuntimeFailed("exit <code>")` and does not branch.

A resume after a dialog answer calls the same runtime adapter with the same `RunRequest` and the same `task` (same `step`, same `payload`). The thread has the question and the answer as untrusted text. The runtime gets no flag that says "resume".

## Cases

| Case | Request |
|---|---|
| Planner call | `RunRequest((), "read", False)`. No capability, no file tool, also for the owner (confirmed decision). |
| `read` step started by the agent owner | `RunRequest((<capability_id>,), "read", True)`. |
| `read` step started by another person | `RunRequest((<capability_id>,), "read", False)`. |
| `approve` step | No request. No runtime runs. `build_run_request` raises `ValueError`. |
| `write` step | After spec 004: `validate_plan` accepts it. In 003 alone: `validate_plan` rejects it and `build_run_request` raises `ValueError`. |

## Rules

1. The core builds the request. The core never reads `runtime.claude`.
2. The adapter checks exposure again at run time. A capability that is not exposed now fails the step (`reason: capability not available`).
3. The request holds no path, no URL, no token, and no tool name.
4. The import-boundary test (T071) proves that no core module imports a runtime-specific module.
