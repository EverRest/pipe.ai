# Contract: Load exposed capabilities into a `--restricted` child

Source: design brief §12 (last item) and §8. Builds on [../../001-adapter-core-status/contracts/runtime-contract.md](../../001-adapter-core-status/contracts/runtime-contract.md). Decision record: [../research.md](../research.md) D6, D7. Flags and behavior were checked with `claude 2.1.325` (research.md P1 to P9).

## Problem

`claude -p --restricted` ignores the user, project, and local settings files. The child does not load the plugins, the personal skills, or the MCP servers of the owner. The adapter must load only the exposed capabilities, explicitly, and keep the file confinement of `--restricted`.

## Interface

```python
# src/pipe/runtime_claude_loadset.py  (pure; part of the `claude` runtime adapter)
def load_set(caps: list[ClaudeCapability], exposed: list[str], capability_ids: list[str]) -> LoadSet: ...

# src/pipe/runtime_claude_load.py  (I/O; stdlib only; part of the `claude` runtime adapter)
def prepare(load: LoadSet, run_dir: Path, mcp_entries: dict[str, dict]) -> PreparedLoad: ...
# PreparedLoad: plugin_dir: Path | None, mcp_file: Path | None, tools: list[str], allowed: list[str]

# src/pipe/runtime_claude.py
def build_cmd(inp, cfg, prepared: PreparedLoad | None = None) -> list[str]: ...
```

`build_cmd` with `prepared=None` gives the exact 001 command (no change). The adapter of 002 passes `None`. 002 does not load exposed capabilities into any run: it provides the builder only (design decision Q2). Specs 003 and 004 send capability IDs and an access level. The `claude` adapter calls `load_set` with those IDs, then `prepare`, passes the `PreparedLoad`, and calls `cleanup`. The core never calls these functions and never imports these modules.

## Command with a `PreparedLoad`

001 command, plus:

```text
--plugin-dir <run_dir>/exposed-plugin          # only if skills or commands are exposed
--mcp-config <run_dir>/mcp.json                # only if MCP servers are exposed (--strict-mcp-config stays)
--tools <001 tools>,Skill                      # Skill added only if skills or commands are exposed
--allowedTools <001 rules> "Skill(pipe-exposed:<name>)" ... "mcp__<server>" ...
```

- `--restricted` and `--permission-mode dontAsk` stay on every run.
- `--tools ""` removes the Skill tool (check P5). A task with an empty tool set therefore cannot run an exposed skill. The `claude` adapter sets the tool list from the request (spec 003 contracts/runtime-request.md).
- Nothing is added when the load set is empty.

## Generated plugin

```text
<run_dir>/exposed-plugin/
├── .claude-plugin/plugin.json      {"name":"pipe-exposed","version":"0.0.0","description":"generated"}
├── skills/<link_name> -> <source skill directory>      (symlink)
└── commands/<link_name>.md                              (copy of the source file)
```

- `<run_dir>` is `~/.pipe/run/<run_id>/` (mode 0700). The caller that called `prepare` removes it with `cleanup` after the run, also after a failure or a timeout.
- The generated plugin has no hooks and no MCP servers. The status hook and the other hooks of the owner do not run (they sit in settings files, which `--restricted` ignores; research.md P6 shows plugin hooks would run, so the plugin is generated instead of loaded whole).
- `link_name` = the directory name of the skill (or the file name of the command). If two exposed items have the same `link_name`, the second (by `id` order) is skipped and `LoadSet.skipped` has a notice.

## MCP file

`<run_dir>/mcp.json` = `{"mcpServers": {<name>: <entry>}}` with only the exposed servers. Entries are copied from `~/.claude.json` (`mcpServers`) or from the plugin that defines them. Mode 0600. It is the only file that holds a full entry. It is removed after the run. A server name that has no entry at run time is skipped and logged (by name only).

## Never

- The adapter never edits `~/.claude/settings.json` or any settings file of the owner.
- No full MCP entry, URL, path, or token goes into a log line, a Slack message, the card, or the prompt.
- The runtime still gets no `hop`, trust, or Slack data (principle VI). The load set is a command-line concern of the adapter.
