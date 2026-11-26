"""Generate the `pipe-exposed` plugin and MCP file for one run (research.md D6, D7)."""

import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from pipe.runtime_claude_loadset import PLUGIN, LoadSet

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedLoad:
    plugin_dir: Path | None
    mcp_file: Path | None
    tools: list[str]
    allowed: list[str]


def prepare(load: LoadSet, run_dir: Path, mcp_entries: dict[str, dict]) -> PreparedLoad:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir.chmod(0o700)
    plugin_dir = None
    if load.needs_skill_tool:
        plugin_dir = run_dir / "exposed-plugin"
        meta = {"name": PLUGIN, "version": "0.0.0", "description": "generated"}
        (plugin_dir / ".claude-plugin").mkdir(parents=True)
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(json.dumps(meta))
        if load.skills:
            (plugin_dir / "skills").mkdir()
        if load.commands:
            (plugin_dir / "commands").mkdir()
        for name, src in load.skills:
            os.symlink(src, plugin_dir / "skills" / name)
        for name, src in load.commands:
            shutil.copyfile(src, plugin_dir / "commands" / f"{name}.md")
    servers = {}
    for s in load.mcp:
        if s in mcp_entries:
            servers[s] = mcp_entries[s]
        else:
            log.warning("mcp server %s has no entry; skipped", s)
    mcp_file = None
    if servers:
        mcp_file = run_dir / "mcp.json"
        fd = os.open(mcp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"mcpServers": servers}, f)
    rules = [r for r in load.allowed_rules if not r.startswith("mcp__") or r[5:] in servers]
    return PreparedLoad(plugin_dir, mcp_file, ["Skill"] if plugin_dir else [], rules)


def cleanup(run_dir: Path) -> None:
    shutil.rmtree(run_dir, ignore_errors=True)
