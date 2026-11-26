"""Agent card: sanitize, build, validate, publish decision. Pure."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from pipe.core.capability import Capability, sanitize_tags
from pipe.core.exposure import state_of
from pipe.core.scrub import scrub

_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://\S+")
_PATH = re.compile(r"(?<![\w/.:~-])(?:~/[\w.~-]+(?:/[\w.~-]+)*|/[\w.~-]+(?:/[\w.~-]+)+)")
_HANDLE = re.compile(r"[A-Za-z0-9._:-]{2,64}")
_FIELDS = {
    "name",
    "description",
    "owner",
    "bot_id",
    "bot_user_id",
    "kind",
    "mode",
    "skills",
    "hash",
}
CARD_EVENT = "pipe.card.v1"


class CardError(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    agent_name: str
    description: str
    owner: str
    bot_id: str
    bot_user_id: str


@dataclass(frozen=True)
class Card:
    name: str
    description: str
    owner: str
    bot_id: str
    bot_user_id: str
    skills: list
    hash: str
    kind: str = "agent"
    mode: str = "laptop"


@dataclass(frozen=True)
class CardState:
    channel: str
    ts: str
    hash: str


def sanitize_text(text: str, limit: int = 200) -> str:
    text = _PATH.sub("[removed]", _URL.sub("[removed]", text))
    return " ".join(scrub(text).split())[:limit]


def skills_hash(skills: list[dict]) -> str:
    s = sorted(skills, key=lambda x: x["id"])
    j = json.dumps(s, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(j.encode()).hexdigest()


def resolve_tags(cap: Capability, tag_map: dict[str, list[str]]) -> tuple[str, ...]:
    """Adapter tags, then the map list (wins) or the declared tags."""
    extra = tag_map.get(cap.id, cap.declared_tags)
    return tuple(dict.fromkeys(cap.tags + sanitize_tags(extra)))


def _entry(cap: Capability, tag_map) -> dict:
    e = {
        "id": cap.id,
        "name": sanitize_text(cap.name),
        "description": sanitize_text(cap.description),
        "tags": list(resolve_tags(cap, tag_map)),
    }
    for k in ("access", "input_schema", "output_schema"):
        if getattr(cap, k) is not None:
            e[k] = getattr(cap, k)
    return e


def build_card(identity: Identity, caps: list[Capability], exposed, tag_map) -> Card:
    if not (identity.owner and identity.bot_id and identity.bot_user_id):
        raise CardError("owner, bot_id, and bot_user_id are required")
    skills = sorted(
        (
            _entry(c, tag_map)
            for c in caps
            if c.role == "item" and state_of(c, exposed) == "exposed"
        ),
        key=lambda e: e["id"],
    )
    return Card(
        name=sanitize_text(identity.agent_name),
        description=sanitize_text(identity.description),
        owner=identity.owner,
        bot_id=identity.bot_id,
        bot_user_id=identity.bot_user_id,
        skills=skills,
        hash=skills_hash(skills),
    )


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def validate_card(card) -> list[str]:
    """Violations; [] means safe. Accepts a Card or its dict form."""
    d = card if isinstance(card, dict) else asdict(card)
    errs = [f"bad field: {k}" for k in sorted(set(d) - _FIELDS)]
    errs += [f"missing field: {k}" for k in sorted(_FIELDS - set(d))]
    if not _HANDLE.fullmatch(str(d.get("bot_user_id", ""))):
        errs.append("bad bot_user_id")
    for s in _strings(d):
        if _URL.search(s):
            errs.append("url in card")
        if _PATH.search(s):
            errs.append("path in card")
        if scrub(s) != s:
            errs.append("token in card")
    return errs


def card_text(card: Card, escape=lambda s: s) -> str:
    """Short readable list for people. `escape` is the transport's mention escape."""
    lines = [f"{card.name} ({card.mode}), owner {card.owner}"]
    lines += [f"{s['id']}: {s['description']}" for s in card.skills]
    return escape("\n".join(lines))


def decide_publish(new_hash: str, existing: CardState | None) -> str:
    if existing is None:
        return "post"
    return "none" if existing.hash == new_hash else "update"


def pick_own_card(messages: list[dict], bot_id: str) -> CardState | None:
    """Newest card message authored by `bot_id`. The payload bot_id is not trusted."""
    best = None
    for m in messages:
        meta = m.get("metadata") or {}
        author = m.get("bot_id") or (m.get("sender_id") if m.get("sender_is_bot") else None)
        if author != bot_id or meta.get("event_type") != CARD_EVENT:
            continue
        if best is None or float(m["ts"]) > float(best["ts"]):
            best = m
    if best is None:
        return None
    h = (best["metadata"].get("event_payload") or {}).get("hash", "")
    return CardState(best.get("channel", ""), best["ts"], h)
