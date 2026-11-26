"""Mention routing. Pure."""

from collections.abc import Callable, Collection
from dataclasses import dataclass

from pipe.core.contract import MentionEvent
from pipe.core.status import is_status_query


@dataclass(frozen=True)
class Decision:
    action: str  # reply | status_query | ignore
    reason: str = ""


def is_owner(sender_id: str, owner: str | None) -> bool:
    """True only for a non-empty owner equal to the sender (fail closed)."""
    return bool(owner) and sender_id == owner


def should_handle(
    event: MentionEvent,
    agent_id: str,
    mention: Callable[[str], str],
    event_ids: Collection[str] = (),
    mention_keys: Collection[str] = (),
    in_flight: Collection[str] = (),
) -> Decision:
    key = f"{event.channel}:{event.ts}"
    if event.sender_is_bot or event.sender_id == agent_id:
        return Decision("ignore", "bot sender")
    if event.event_id and (event.event_id in event_ids or event.event_id in in_flight):
        return Decision("ignore", "event handled")
    if key in mention_keys or key in in_flight:
        return Decision("ignore", "mention handled")
    tag = mention(agent_id)
    if tag not in event.text:
        return Decision("ignore", "no mention")
    if is_status_query(event.text, tag):
        return Decision("status_query", "status query")
    return Decision("reply", "mention")
