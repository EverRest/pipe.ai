"""Step claims. Pure."""

from collections.abc import Callable


def ts_key(ts: str) -> tuple[int, int]:
    """Message ts as numbers: (seconds, microseconds)."""
    s, _, us = ts.partition(".")
    return int(s), int(us or 0)


def resolve_claim(claims):
    """Winner: lowest ts; an equal ts goes to the lower `by` string (stable, input-order free).
    `failed` claims are dropped. No claim gives None."""
    live = [c for c in claims if c.status != "failed"]
    return min(live, key=lambda c: (ts_key(c.ts), c.by), default=None)


def claim_excluded(step, agent_id: str, holder: Callable[[int], str | None]) -> bool:
    """True when `agent_id` holds a step listed in `step.exclude_agents_of`.
    `holder(j)` gives the agent of step j (step_agent), or None."""
    return any(holder(j) == agent_id for j in step.exclude_agents_of or ())
