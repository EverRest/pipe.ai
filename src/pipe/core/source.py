"""Plan source and hop limit by source. Pure."""

import re

MAX_HOP_FREE = 3
MAX_HOP_TEMPLATE = 5
_SRC = re.compile(r"template:([a-z0-9-]{1,32})@([0-9a-f]{32})")


def parse_source(source) -> tuple[str, str] | None:
    """`template:<name>@<hash>` gives (name, hash). Anything else gives None."""
    m = _SRC.fullmatch(source) if isinstance(source, str) else None
    return m.groups() if m else None


def hop_limit(effective: str) -> int:
    return MAX_HOP_TEMPLATE if effective == "template" else MAX_HOP_FREE


def effective_source(plan, flows, cards, starter) -> str:
    """`template` only when the claim is verified by a local flow. Else `free`."""
    try:
        p = parse_source(getattr(plan, "source", None))
        flow = (flows or {}).get(p[0]) if p else None
        ok = flow is not None and flow.hash == p[1] and flow.matches(plan.steps, cards, starter)
        return "template" if ok else "free"
    except Exception:
        return "free"
