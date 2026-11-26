"""Core capability type, notice, and tag clean-up. Pure, runtime-agnostic."""

import re
from dataclasses import dataclass

ROLES = ("item", "group", "listed_only")
_TAG = re.compile(r"[a-z0-9-]{1,32}")


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    description: str = ""
    role: str = "item"  # item | group | listed_only
    open: bool = False  # adapter proved the item safe (role item only)
    group: str | None = None
    tags: tuple[str, ...] = ()
    declared_tags: tuple[str, ...] = ()
    runtime: str = "claude"
    access: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    classified: bool = True

    def __post_init__(self):
        if not self.id or not self.name:
            raise ValueError("id and name must not be empty")
        if self.role not in ROLES:
            raise ValueError(f"bad role: {self.role}")


@dataclass(frozen=True)
class Notice:
    kind: str
    id: str
    text: str


def sanitize_tags(raw) -> tuple[str, ...]:
    """Keep valid tags in order, no duplicates, at most 8."""
    out = dict.fromkeys(t for t in (raw or ()) if isinstance(t, str) and _TAG.fullmatch(t))
    return tuple(out)[:8]
