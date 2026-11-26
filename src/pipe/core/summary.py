"""Owner summary text and DM decision. Pure."""

import hashlib
from dataclasses import dataclass

from pipe.core.capability import Capability, Notice
from pipe.core.card import unsafe
from pipe.core.exposure import state_of
from pipe.core.scrub import scrub


@dataclass(frozen=True)
class Summary:
    text: str
    hash: str


def build_summary(caps: list[Capability], exposed, notices: list[Notice]) -> Summary:
    n_exp = sum(state_of(c, exposed) == "exposed" for c in caps)
    n_skip = sum(n.kind == "skipped" for n in notices)
    lines = [f"{n_exp} exposed, {len(caps) - n_exp} owner-only, {n_skip} skipped"]
    # a notice with a URL, a path, or a token is replaced (same rules as the card)
    lines += sorted(f"{n.kind}: {'[removed]' if unsafe(n.text) else n.text}" for n in notices)
    text = scrub("\n".join(lines))
    return Summary(text, hashlib.sha256(text.encode()).hexdigest())


def decide_dm(new_hash: str, last_hash: str | None) -> str:
    return "none" if new_hash == last_hash else "send"
