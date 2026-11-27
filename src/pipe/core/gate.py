"""Owner gate for write steps. Pure."""

from collections.abc import Iterable, Sequence

from pipe.core.claim import ts_key


def in_allowlist(allowlist: Sequence[str], subject: str | None) -> bool:
    """Exact match. None and "" never match."""
    return bool(subject) and subject in allowlist


def gate_required(step, starter: str | None, owner: str | None, humans: Iterable[str] = ()) -> bool:
    """A `write` step needs the gate unless the owner started the thread AND every
    human message in it is the owner's (DQ1). `humans` are the human sender ids.
    `step.access` comes from the plan, never from `next.access`."""
    trusted = bool(owner) and starter == owner and all(h == owner for h in humans)
    return step.access == "write" and not trusted


def gate_decision(
    sender: str, starter: str | None, sender_owner: str | None, allowlist: Sequence[str]
) -> str:
    """ "auto" only when the sender is allowlisted AND the starter is trusted (DQ2)."""
    trusted = bool(starter) and (
        (bool(sender_owner) and starter == sender_owner) or in_allowlist(allowlist, starter)
    )
    return "auto" if in_allowlist(allowlist, sender) and trusted else "button"


def step_rejected(claims: Iterable, step_index: int) -> bool:
    """True when the latest claim of the step is `failed` with `reason: rejected` (FR-046)."""
    mine = [c for c in claims if c.step == step_index]
    last = max(mine, key=lambda c: ts_key(c.ts), default=None)
    return bool(last) and last.status == "failed" and last.reason == "rejected"


def gate_text(step_no: int, total: int, agent: str, owner_id: str, sender: str) -> str:
    """Gate message. Names must be escaped by the caller; only the owner mention is real."""
    return (
        f"Step {step_no} of {total} (write, {agent}): needs approval. "
        f"<@{owner_id}> Accept or reject this work from {sender}."
    )
