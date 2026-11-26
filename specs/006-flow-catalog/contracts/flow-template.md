# Contract: Flow template file

Source: owner decisions 1, 4, and 5 for spec 006. Spec FR-001 to FR-005, FR-014 to FR-019. The loader is in `src/pipe/flows_io.py`. The rules are the pure function `validate_flow` in `src/pipe/core/flows.py`.

## Where the files are

| Place | Path | Who edits |
|---|---|---|
| Shared (git) | `flows/<name>.yaml` in the team repository. The config key `flows_dir` can change the path. | The team, by merge request. |
| Override | `~/.pipe/flows/<name>.yaml` | One owner. |

An override file wins over the shared file with the same name. An invalid override file does not hide a valid shared file. The loader reads `.yaml` files only. It never writes in these directories.

## File format

YAML, read with `yaml.safe_load` (pyyaml is a project dependency). A file is at most 20 000 bytes.

```yaml
name: bugfix                  # equals the file name without .yaml. ^[a-z0-9-]{1,32}$
version: 1                    # the schema version. Must be 1.
description: "Fix a bug with a failing test first."   # 1 to 200 characters
params:                       # optional
  check:                      # key: ^[a-z]{1,16}$
    values: [e2e, deps-check] # 2 to 8 tags from the vocabulary
    default: e2e              # one of values
steps:                        # 1 to 6 entries
  - id: reproduce             # ^[a-z0-9-]{1,32}$, unique in the file
    agent: any                # any | $agent | $starter (human step only)
    capability: "tag:reproduce"   # tag:<tag> | tag:$<param>. Absent on a human step.
    access: read              # optional. Must equal the default access of the tag.
    goal: "Write a failing test for: {goal}"   # 1 to 300 characters
    payload: {}               # optional static object, at most 500 characters as JSON
    gate: approval            # optional. Only the value approval.
    exclude_agents_of: [implement]   # optional. Ids of EARLIER steps.
    on_fail: troubleshoot     # optional. At most one in the file.
```

Allowed top-level keys: `name`, `version`, `description`, `params`, `steps`. Allowed step keys: `id`, `agent`, `capability`, `access`, `goal`, `payload`, `gate`, `exclude_agents_of`, `on_fail`. Any other key is an error.

## Placeholders

| Placeholder | Where | Meaning |
|---|---|---|
| `{goal}` | `goal` text | The goal text of the mention (without the `flow:` words and the mentions). |
| `{<param>}` | `goal` text | The value of the parameter. |
| `tag:$<param>` | `capability` | The tag is the value of the parameter. |
| `$agent` | `agent` | The first agent named in the message after the planner. At most one step uses it. |
| `$starter` | `agent` (human step) | The thread starter. The step becomes `human:<starter id>`. |

No other placeholder exists. A `$` or `{` that is not in this table is an error.

## Rules (`validate_flow(data, stem, tags) -> list[str]`)

Each error is a fixed sentence with the file name or the step id. An empty list means the file is valid. `tags` is the vocabulary (data, from `flows/tags.yaml`).

1. The file is a mapping with the allowed keys only. `version` is 1.
2. `name` matches the pattern and equals `stem`.
3. `description` is not empty and has at most 200 characters.
4. `params`: each key matches the pattern. `values` has 2 to 8 entries. Each value is a tag of the vocabulary. `default` is in `values`. A parameter that no step uses is an error.
5. `steps` has 1 to 6 entries. At most 5 are agent steps (steps with a `capability`). At most 1 is a human step.
6. Each `id` is unique and matches the pattern.
7. An agent step has `agent` equal to `any` or `$agent`, and `capability` equal to `tag:<tag>` or `tag:$<param>`. A fixed tag is in the vocabulary. At most one step has `$agent`. A concrete bot ID, user ID, plugin name, or tool name in `agent` is an error.
8. `access` of an agent step, when present, equals the default access of its tag (for `tag:$<param>`: the default access of every value is the same, else an error). When absent, the default applies.
9. A human step has `agent: "$starter"`, `access: approve`, and no `capability`. It is the last step. It has no `gate`, no `on_fail`, no `exclude_agents_of`, and no `payload`.
10. `exclude_agents_of` lists ids of earlier steps. A step cannot name itself or a later step. Each named step is an agent step.
11. At most one step has `on_fail`. Its value is the id of the last step. The last step is an agent step. The step with `on_fail` is not the last step. The last step has no `on_fail`. A file with `on_fail` has no human step. (The last step is the branch step.)
12. `gate`, when present, is `approval`.
13. `goal` has 1 to 300 characters. `payload` is a mapping of at most 500 characters as canonical JSON.
14. No string in the file holds `://`, an absolute path (`/Users/`, `/home/`, `~/`), or a string that `scrub` changes (a token). No string names a plugin, a skill, or an MCP server (checked by a fixed word list in the loader tests, not in the core).
15. The count of agent steps is at most `MAX_HOP_TEMPLATE` (5, defined in spec 003 `core/source.py`).

## Branch step semantics

The last step of a file with `on_fail` is the branch step. On the success path it is skipped. The flow is `done` after the step before it. On the failure path (`run_failed`, spec FR-016) the flow goes from the failed step to the branch step. The flow ends after the branch step, whether it is `done` or `failed`. A "Retry" on the failed source step is not offered when the branch handoff was posted.

## Expansion (`expand_flow(flow, goal, params, cards, starter, mentions) -> (steps, errors)`)

1. Resolve `params`: a given value must be in `values`, else the error `flow <name>: bad value for <key>`. A missing value takes the default. An unknown key gives `flow <name>: unknown parameter <key>`.
2. Resolve `$agent`: needs one entry in `mentions` (agent IDs after the planner), else `flow <name> needs a second agent mention`. A flow with no `$agent` and one or more extra mentions gives `flow <name> takes no agent mention`.
3. Compute the missing tags: for each tag step, the tag must be offered by a trusted card (`matches_tag`). For the `$agent` step, the named card must offer the tag. All missing tags go in one error: `flow <name>: missing tags: <tag>, <tag>` (sorted, no duplicates). The expansion stops here when the list is not empty.
4. Build each step: ids become indexes. `{goal}` and `{<param>}` are replaced. A goal over 500 characters gives `flow <name>: goal too long`. A `$agent` step gets the agent ID and the lowest capability ID of that card that has the tag and a fitting access. A `$starter` step gets `human:<starter>`.
5. The result is a list of plan steps (003 plan-schema plus `gate`, `on_fail`, `exclude_agents_of`). The caller adds `source` and runs `validate_plan`.

`expand_flow` is deterministic. It reads no file and calls no LLM.
