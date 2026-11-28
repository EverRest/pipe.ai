"""Classification and core mapping for Claude Code items (research.md D3, D17)."""

from pipe.core.capability import Capability
from pipe.runtime_claude_capability import ClaudeCapability

SAFE_TOOLS = frozenset({"Read", "Grep", "Glob"})


def classify(cap: ClaudeCapability, library=()) -> str:
    """`open` only when the tool list is proven safe and no credential signal exists.

    Items of a library marketplace are other people's code: always `owner-only`.
    """
    if cap.marketplace is not None and cap.marketplace in library:
        return "owner-only"
    ok = cap.type in ("skill", "command") and cap.allowed_tools and not cap.signals
    return "open" if ok and set(cap.allowed_tools) <= SAFE_TOOLS else "owner-only"


def to_core(cap: ClaudeCapability, library=()) -> Capability:
    base = dict(
        id=cap.id,
        name=cap.name,
        description=cap.description,
        declared_tags=cap.declared_tags,
        runtime="claude",
        access=None,
        classified=True,
    )
    if cap.type in ("skill", "command"):
        tags = (cap.type, *([cap.plugin] if cap.plugin else []))
        return Capability(
            **base,
            role="item",
            open=classify(cap, library) == "open",
            group=cap.plugin_id,
            tags=tags,
        )
    role = {"mcp": "item", "plugin": "group"}.get(cap.type, "listed_only")
    return Capability(**base, role=role, open=False, group=None, tags=(cap.type,))
