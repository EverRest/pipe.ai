"""Discover Claude Code capabilities from local files (research.md D1, D5). Names only."""

import json
from pathlib import Path

from pipe.core.capability import Notice
from pipe.runtime_claude_capability import ClaudeCapability, assign_ids, from_text


def _json(p: Path):
    try:
        return json.loads(p.read_text())
    except OSError, ValueError:
        return None


def _enabled_plugins(home: Path) -> list[tuple[str, Path]]:
    """(name, install dir) of enabled plugins. Reads only `enabledPlugins` from settings."""
    s = _json(home / ".claude" / "settings.json")
    on = s.get("enabledPlugins") if isinstance(s, dict) else None
    inst = _json(home / ".claude" / "plugins" / "installed_plugins.json")
    plugins = inst.get("plugins") if isinstance(inst, dict) else None
    out = []
    for key, entries in sorted((plugins if isinstance(plugins, dict) else {}).items()):
        if not (isinstance(on, dict) and on.get(key) is True and entries):
            continue
        path = Path(entries[0].get("installPath", ""))
        meta = _json(path / ".claude-plugin" / "plugin.json")
        name = meta.get("name") if isinstance(meta, dict) else None
        out.append((str(name or key.split("@")[0]), path))
    return out


def _servers(v) -> dict:
    if isinstance(v, dict):
        v = v.get("mcpServers", v)
    return {k: e for k, e in v.items() if isinstance(e, dict)} if isinstance(v, dict) else {}


def _plugin_mcp(path: Path) -> dict:
    meta = _json(path / ".claude-plugin" / "plugin.json")
    ref = meta.get("mcpServers") if isinstance(meta, dict) else None
    out = _servers(_json(path / ref) if isinstance(ref, str) else ref)
    return out | _servers(_json(path / ".mcp.json"))


def read_mcp_entries(home: Path) -> dict[str, dict]:
    """Full entries (may hold secrets). Run time only (research.md D7). User scope wins."""
    out: dict[str, dict] = {}
    for _, path in _enabled_plugins(home):
        out |= _plugin_mcp(path)
    j = _json(home / ".claude.json")
    return out | _servers(j.get("mcpServers") if isinstance(j, dict) else None)


def _items(type: str, root: Path, plugin: str | None, notices: list[Notice]):
    """Skills (`<root>/skills/*/SKILL.md`) or commands (`<root>/commands/*.md`)."""
    if type == "skill":
        found = [(d.name, d / "SKILL.md", d) for d in sorted((root / "skills").glob("*/"))]
        found = [f for f in found if f[0] != "synced" and f[1].is_file()]
    else:
        found = [(f.stem, f, f) for f in sorted((root / "commands").glob("*.md"))]
    for name, file, src in found:
        try:
            yield from_text(type, name, file.read_text(), str(src), plugin)
        except OSError, ValueError:
            notices.append(
                Notice("skipped", f"{type}:{name}", f"{type}:{name} skipped: unreadable")
            )


def discover(home: Path, repo_roots: list[str]) -> tuple[list[ClaudeCapability], list[Notice]]:
    home, notices, caps = Path(home), [], []
    for type in ("skill", "command"):
        caps += _items(type, home / ".claude", None, notices)
    j = _json(home / ".claude.json")
    for n in _servers(j.get("mcpServers") if isinstance(j, dict) else None):
        caps.append(ClaudeCapability(id="", type="mcp", name=n, source=str(home / ".claude.json")))
    for name, path in _enabled_plugins(home):
        caps.append(ClaudeCapability(id="", type="plugin", name=name, source=str(path)))
        for type in ("skill", "command"):
            caps += _items(type, path, name, notices)
        for n in _plugin_mcp(path):
            caps.append(
                ClaudeCapability(id="", type="mcp", name=n, plugin=name, source=f"{path}#{n}")
            )
    for root in repo_roots:
        for d in sorted(Path(root).expanduser().glob("*/")):
            if (d / ".git").exists():
                caps.append(ClaudeCapability(id="", type="repo", name=d.name, source=str(d)))
    return assign_ids(caps), notices
