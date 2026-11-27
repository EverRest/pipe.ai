"""Trigger bot rules. Pure. No tool names; the route gives the flow word."""

import re
from dataclasses import dataclass, fields

from pipe.core.gate import in_allowlist
from pipe.core.pipeline import Pipeline, Step
from pipe.core.scrub import scrub
from pipe.core.trust import trusted_sender

MAX_TITLE = 200
_STEP_FIELDS = {f.name for f in fields(Step)}


@dataclass(frozen=True)
class Trigger:
    ts: str
    sender: str
    pipeline: Pipeline | None  # form A; the source is never read from the payload
    flow: str | None  # form B
    title: str


def is_trigger_card(card) -> bool:
    """A trigger bot has `kind: trigger` and no skills (FR-015)."""
    return isinstance(card, dict) and card.get("kind") == "trigger" and not card.get("skills")


def _pipeline(raw) -> Pipeline | None:
    try:
        steps = tuple(
            Step(**{k: v for k, v in s.items() if k in _STEP_FIELDS}) for s in raw["steps"]
        )
    except Exception:
        return None
    return Pipeline(steps) if steps else None


def _title(text: str, flow: str | None) -> str:
    text = re.sub(r"<[^>]*>", " ", text or "")  # drop mentions and links
    words = [w for w in text.split() if w != f"flow:{flow}"]
    return scrub(" ".join(words))[:MAX_TITLE].strip()


def parse_trigger(msg, cards, flow: str | None) -> Trigger | None:
    """A Trigger, or None. The route gives the reason. `validate_plan` runs later."""
    p, card = msg.payload, cards.get(msg.sender_id)
    if msg.thread_ts not in (None, "", msg.ts):
        return None
    if not (is_trigger_card(card) and trusted_sender(msg, cards) and isinstance(p, dict)):
        return None
    hop = p.get("hop")
    if not (
        p.get("v") == 1
        and p.get("phase") == "plan"
        and p.get("status") == "needs_approval"
        and p.get("by") == msg.sender_id
        and hop == 0
        and not isinstance(hop, bool)
        and "next" not in p
    ):
        return None
    title = _title(getattr(msg, "text", ""), flow)
    if "pipeline" in p:
        pipe = _pipeline(p["pipeline"])
        if pipe is None or flow is not None:
            return None
        return Trigger(msg.ts, msg.sender_id, pipe, None, title)
    if flow is None:  # an empty goal is allowed for a flow (006)
        return None
    return Trigger(msg.ts, msg.sender_id, None, flow, title)


def decide_trigger(sender: str | None, allowlist) -> tuple[str, str]:
    """(action, reason): allow when the sender is in the allowlist, else ask."""
    if in_allowlist(allowlist, sender):
        return ("allow", "allowlisted")
    return ("ask", "not_allowlisted")
