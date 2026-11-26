# Contract: Runtime (adapter to runtime)

Source: design brief §5.1. The runtime does not know `hop`, trust, or Slack. The adapter does all checks.

## Interface (`ports.RuntimePort`)

```python
class RuntimePort(Protocol):
    def run(self, inp: RuntimeInput) -> RuntimeOutput: ...   # raises RuntimeFailed
```

## RuntimeInput

| Field | Type | Note |
|---|---|---|
| `thread` | list[{user: str, text: str}] | Messages of this thread only. User is a display label, not a Slack ID. |
| `task` | {id: str, purpose: str, from_agent: str?, owner: str?, hop: int?, pipeline: any?, step: int?} | 001 sends `id` and `purpose="chat"`. Later specs add the values `plan` and `step`. Other keys are reserved for specs 002 to 004. 001 never sends trust or Slack data in them. |
| `requester_is_owner` | bool | `is_owner(sender_id, owner)` (false when `owner` is empty). The `claude` adapter turns it into a `ToolPolicy` with `tools_for` (`src/pipe/runtime_claude_tools.py`). For the owner: the config key `runtime.claude.owner_tools` (default `Read`, `Grep`, `Glob`) and `disallowed` = `effective_deny_rules(runtime.claude.deny_rules)` (always has `Bash(git push:*)`). For a sender who is not the owner: `tools=[]`, `allowed=[]`, `disallowed=[]`. `restricted` is `true` for every sender. The core holds no `ToolPolicy` type and no tool name. |
| `request` | RunRequest? | Added by spec 003 (capabilities, access, `requester_is_owner`, optional `target`, optional `output_schema`). Not set in 001. |

Note: the brief lists `hop` in `task`. 001 leaves it unset. The adapter checks `hop` before it calls the runtime; the `claude -p` implementation does not put it in the prompt.

## RuntimeOutput

| Field | Type | Note |
|---|---|---|
| `text` | str | Reply for the thread. The adapter scrubs it. |
| `status` | `done` \| `needs_approval` \| `waiting` \| `failed` \| `delegate` | 001 acts on `done` and `failed`. Other values are posted as `text` only. `waiting` with `reason: needs_input` means that `text` is a question for a person (spec 003 runs the dialog). |
| `reason` | str? | Optional. At most 200 characters. Scrubbed. Used with `waiting` and `failed`. |
| `proposal` | object? | Optional proposed plan (at most 4000 characters as canonical JSON). 001 ignores it. Spec 003 checks it with `validate_plan` and shows it for approval. A step never starts work by itself. |
| `next` | {agent, access, payload}? | Parsed. Ignored in 001. |
| `artifacts` | list[str] | Parsed. Appended to the reply as lines in 001. |
| `data` | object? | Optional structured result. 001 ignores it. Spec 003 validates it against the `output_schema` of the capability, when there is one. |

## Other runtime adapters

The contract is the same for every adapter. Spec 003 adds the adapters `exec` (a local command) and `http` (a POST to a URL) for capabilities that the owner declares in config (spec 002). See [runtime-exec-http.md](runtime-exec-http.md). Every adapter applies `scrub` to `text`, `reason`, and `artifacts` and the Transport `escape_mentions` to `text` before it returns.

When the request has an `output_schema`, the adapter passes it to the runtime if the runtime supports it. For `claude`, the adapter merges it as the schema of the property `data` into the `--json-schema` value. For `exec` and `http`, it goes in the input (see runtime-exec-http.md). The core then validates `data` (spec 003). Without a schema, nothing changes.

## `claude -p` implementation

Command (flags checked with `claude --help`):

```text
claude -p --output-format json --json-schema <RuntimeOutput schema>
       --no-session-persistence --strict-mcp-config
       --restricted --permission-mode dontAsk
       --tools <list> [--allowedTools <rules>] [--add-dir <root>...]
       [--disallowedTools <rules>] [--model <model>] [--max-budget-usd <amount>]
```

- `--restricted` and `--permission-mode dontAsk` are passed for every run (owner and non-owner).
- For the owner, `--allowedTools` has one rule per tool per `runtime.claude.repo_roots` entry, for example `"Read(//<root>/**)" "Grep(//<root>/**)" "Glob(//<root>/**)"`. `--add-dir` is passed for each root after the first. A path outside the roots is refused (FR-018; research.md D8, A8).
- For the owner, `--disallowedTools` has every entry of the effective deny list: `Bash(git push:*)` always, plus the entries of `runtime.claude.deny_rules` (the owner can only add rules). The deny rules apply also when the owner widens `owner_tools` (FR-019).
- For a sender who is not the owner, the adapter passes `--tools ""` (an empty value, always present) and nothing else about tools: no `--allowedTools`, no `--add-dir`, and no deny rules. The tool set is empty, so a deny rule has no effect. The runtime has no tools and reads no file. The agent answers from the thread text only (FR-016).
- Prompt on stdin. `cwd` = first `runtime.claude.repo_roots` entry.
- Timeout = `step_timeout_min` minutes. On timeout the process is killed and `RuntimeFailed("timeout")` is raised.
- Tokens are removed from the child environment. The adapter sets `PIPE_RUNTIME=1` in the child environment, so the owner's status hooks do nothing inside the child (the hook rule: `PIPE_RUNTIME` set and non-empty).
- `--max-budget-usd <amount>` is passed only when the config key `max_budget_usd` is set (flag checked with `claude --help`).
- Failure modes: command not found, non-zero exit, timeout, output not valid JSON or not matching the schema. All raise `RuntimeFailed(reason)`.

## Adapter reply on failure (FR-014)

`I could not finish this task. Reason: <reason, scrubbed, max 200 characters>.`
