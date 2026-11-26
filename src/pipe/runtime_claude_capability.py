"""Claude Code capability type and pure helpers (data-model.md ClaudeCapability)."""

import hashlib
import re
from dataclasses import dataclass, replace

import yaml

from pipe.core.capability import sanitize_tags


@dataclass(frozen=True)
class ClaudeCapability:
    id: str
    type: str  # skill | command | mcp | plugin | repo
    name: str
    description: str = ""
    declared_tags: tuple[str, ...] = ()
    plugin: str | None = None
    plugin_id: str | None = None
    allowed_tools: tuple[str, ...] | None = None
    signals: tuple[str, ...] = ()
    source: str = ""  # INTERNAL local path. Never shown.

    @property
    def source_key(self) -> str:
        return self.source


# (name, regex). Case-insensitive. research.md D3.
_SIGNALS = [
    ("mcp__", r"mcp__"),
    ("url", r"https?://"),
    ("token", r"token"),
    ("api key", r"api[ _]key"),
    ("secret", r"secret"),
    ("password", r"password"),
    ("credential", r"credential"),
    ("oauth", r"oauth"),
    ("login", r"login"),
    (".env", r"\.env\b"),
    ("env-secret", r"\b\w+_(?:token|key|secret)\b"),
    ("git push", r"git\s+push"),
    *[
        (c, rf"\b{c}\b")
        for c in [
            "curl",
            "wget",
            "ssh",
            "scp",
            "glab",
            "kubectl",
            "gcloud",
            "docker",
            "psql",
            "mysql",
        ]
    ],
    ("gh", r"\bgh\s"),
    ("aws", r"\baws\s"),
]
_SIGNAL_RES = [(n, re.compile(r, re.I)) for n, r in _SIGNALS]


def find_signals(text: str) -> tuple[str, ...]:
    return tuple(n for n, r in _SIGNAL_RES if r.search(text))


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"---[ \t]*\n(.*?\n)?---[ \t]*(?:\n|$)", text, re.S)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1) or "") or {}
    except yaml.YAMLError as e:
        raise ValueError("invalid frontmatter") from e
    if not isinstance(fm, dict):
        raise ValueError("invalid frontmatter")
    return fm, text[m.end() :]


def _tools(v) -> tuple[str, ...] | None:
    if v is None:
        return None
    items = v.split(",") if isinstance(v, str) else v if isinstance(v, list) else []
    return tuple(str(i).strip() for i in items if str(i).strip())


def from_text(type: str, default_name: str, text: str, source: str, plugin: str | None = None):
    """Build a skill or command item. Raises ValueError for bad frontmatter. `id` is set later."""
    fm, _ = parse_frontmatter(text)
    name = (fm.get("name") if type == "skill" else None) or default_name
    return ClaudeCapability(
        id="",
        type=type,
        name=str(name),
        description=str(fm.get("description") or "").strip(),
        declared_tags=sanitize_tags(fm.get("tags")),
        plugin=plugin,
        allowed_tools=_tools(fm.get("allowed-tools")),
        signals=find_signals(text),
        source=source,
    )


def _base(c: ClaudeCapability) -> str:
    return ":".join([c.type, *([c.plugin] if c.plugin and c.type != "plugin" else []), c.name])


def assign_ids(caps: list[ClaudeCapability]) -> list[ClaudeCapability]:
    """Stable IDs: `<type>[:<plugin>]:<name>`; a collision adds `#<6 hex of sha256(source)>`."""
    bases = [_base(c) for c in caps]
    ids = [
        b + "#" + hashlib.sha256(c.source_key.encode()).hexdigest()[:6] if bases.count(b) > 1 else b
        for b, c in zip(bases, caps, strict=True)
    ]
    plugins = [(c, i) for c, i in zip(caps, ids, strict=True) if c.type == "plugin"]
    out = []
    for c, i in zip(caps, ids, strict=True):
        pid = next(
            (pi for p, pi in plugins if c.plugin == p.name and c.source.startswith(p.source + "/")),
            None,
        )
        out.append(replace(c, id=i, plugin_id=pid if c.type != "plugin" else None))
    return out
