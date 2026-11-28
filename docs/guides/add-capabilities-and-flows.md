# Add capabilities and flows

A capability is something that your agent can do. Other agents see only exposed capabilities.
Restart the adapter after each change.

## 1. See the capabilities

```sh
.venv/bin/pipe capabilities
```

The adapter finds these items:

- Skills and commands in `~/.claude`.
- Enabled plugins, with their skills, commands, and MCP servers.
- MCP servers in `~/.claude.json`.
- Git repositories directly under each `repo_roots` path. They are listed only. You cannot expose them.

An ID has the form `<type>:<name>` or `<type>:<plugin>:<name>`. Copy the ID from the list.

## 2. Expose a skill

```yaml
exposed:
  - skill:<NAME>
  - skill:<PLUGIN>:<NAME>
```

A `plugin:<NAME>` entry exposes all skills and commands of the plugin. This includes items that use credentials.

A skill or command is exposed with no entry when all these are true:

- Its `allowed-tools` is set and holds only `Read`, `Grep`, `Glob`.
- Its text has no credential signal, for example `token`, `password`, a URL, or `curl`.
- It is not from a marketplace in `library_marketplaces`.

## 3. Declare an `exec` capability

```yaml
capabilities:
  - id: <ID>
    name: <NAME>
    description: <TEXT>
    access: read
    runtime: exec
    command: [/absolute/path/to/program, <ARG>]
    env_allow: [<VAR_NAME>]
    timeout_s: 600
    input_schema:
      type: object
exposed: [exec:<ID>]
```

- `id`, `name`, `description`, `access`, `runtime`, and `command` are required.
- `access` must be `read`.
- The first item of `command` must be an absolute path.
- An exposed `exec` capability must have `input_schema`.
- A schema with `additionalProperties: false` must list `context` and `artifacts`.
- The program runs as your OS user with no sandbox. It runs in a new directory under `~/.pipe/run/`.

Input on stdin:

```json
{"goal": "...", "task": {"id": "...", "step": 0}, "payload": {}, "output_schema": {}}
```

`payload` and `output_schema` are present only when they exist.

Output on stdout:

```json
{"status": "done", "text": "...", "artifacts": ["https://..."], "files": ["report.txt"]}
```

- `text` and `status` are required.
- `artifacts` keeps only `https` links.
- `files` are relative paths inside the run directory, at most 10 MB each.
- For a check that failed, print `"status": "failed"` and exit 0. Only this can start an `on_fail` branch.
- A non-zero exit fails the step and starts no branch.

## 4. Declare an `http` capability

```yaml
capabilities:
  - id: <ID>
    name: <NAME>
    description: <TEXT>
    access: read
    runtime: http
    url: https://<HOST>/<PATH>
    token: keychain:<SERVICE>
    timeout_s: 60
exposed: [http:<ID>]
```

- `url` must use `https`. `http` is allowed only for `localhost` and `127.0.0.1`.
- `token` is optional. The Keychain account is `token`. The adapter sends it as a bearer token.
- The adapter sends a POST with the same JSON as for `exec`. It follows no redirect.

```sh
security add-generic-password -U -s <SERVICE> -a token -w <TOKEN>
```

## 5. Tag a capability

Flows select capabilities by tag.

```yaml
tags:
  skill:<NAME>: [review]
  exec:<ID>: [e2e]
```

- At most 8 tags. A tag uses `a-z`, `0-9`, `-`, at most 32 characters.
- A skill can also have `tags` in its frontmatter. The config entry replaces them.
- The vocabulary is in [flows/tags.yaml](../../flows/tags.yaml).
- If more than one exposed capability has the tag, the lowest ID wins.
- A declared capability is `read`. It cannot serve a `write` tag, for example `implement`.

## 6. Add or override a flow template

Put your file in `~/.pipe/flows/<name>.yaml`. A file with the same name as a shared flow wins.
A shared flow goes in `flows/` with an MR.

```yaml
name: <name>          # must equal the file name
version: 1
description: "..."    # 1 to 200 characters
steps:
  - id: check
    agent: any
    capability: "tag:e2e"
    goal: "Run the tests: {goal}"
  - id: approve
    agent: "$starter"
    access: approve
    goal: "Approve the result."
```

Rules:

- 1 to 6 steps. At most 5 agent steps.
- `agent` is `any`, `$agent` (one step at most), or `$starter` (the last step only).
- `capability` is `tag:<tag>` or `tag:$<param>`. The tag must be in `flows/tags.yaml`.
- `goal` has 1 to 300 characters.
- Optional: `params`, `payload`, `gate: approval`, `exclude_agents_of`, `on_fail`.
- No URL, absolute path, home path, or token.
- File size at most 20000 bytes.

```sh
.venv/bin/pipe flows validate <name>
.venv/bin/pipe flows show <name>
```

An override changes the template hash. Other adapters then see the plan as `free`, with `hop` 3 or less.
Give all adapters the same file.

## 7. Use the plugin library (spec 007)

The library is a separate git repository in Claude Code marketplace format. It is not part of this repository.
The real library repository and the release note are not done.

1. Add the marketplace with the Claude Code plugin tools. Keep auto-update OFF.
2. Install a plugin at a fixed version.
3. Add the marketplace name to the config:

```yaml
library_marketplaces: [pipe-library]
```

4. Run `pipe capabilities`. Library items show as `owner-only`.
5. Review the code of an item. Then add its ID to `exposed`.

An enabled plugin comes from `enabledPlugins` in `~/.claude/settings.json`.
See [spec 007](../../specs/007-plugin-library/spec.md).
