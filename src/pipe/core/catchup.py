"""Catch-up selection. Pure."""

from collections.abc import Callable, Collection

from pipe.core.contract import Message


def parents_to_scan(history: list[Message], last_seen_ts: str) -> list[Message]:
    """Parents with a newer reply, and top-level messages newer than last_seen_ts."""
    last = float(last_seen_ts)
    return [
        m
        for m in history
        if (m.latest_reply and float(m.latest_reply) > last) or float(m.ts) > last
    ]


def pick_missed(
    messages: list[Message],
    bot_user_id: str,
    last_ts: str,
    handled: Collection[str],
    mention: Callable[[str], str],
) -> list[Message]:
    """Unhandled mentions of the agent newer than last_ts, oldest first."""
    last, tag = float(last_ts), mention(bot_user_id)
    out = []
    for m in messages:
        if m.sender_id == bot_user_id or tag not in m.text or float(m.ts) <= last:
            continue
        if f"{m.channel}:{m.ts}" in handled:
            continue
        if any(
            r.sender_id == bot_user_id and r.thread == m.thread and float(r.ts) > float(m.ts)
            for r in messages
        ):
            continue
        out.append(m)
    return sorted(out, key=lambda m: float(m.ts))
