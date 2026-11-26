"""Pure Slack mapping. No Slack library import."""

import re

id_pattern = r"^[BUW][A-Z0-9]{2,}$"

_MENTION = re.compile(r"<([@!][^>]*)>")


def message_fields(raw: dict, channel: str, event_id: str | None = None) -> dict:
    """Slack message dict to the field dict of a neutral `Message`."""
    bot_id = raw.get("bot_id")
    return {
        "channel": channel,
        "ts": raw["ts"],
        "thread": raw.get("thread_ts") or raw["ts"],
        "sender_id": bot_id or raw.get("user"),
        "sender_is_bot": bool(bot_id),
        "sender_handle": raw.get("user"),
        "text": raw.get("text", ""),
        "metadata": raw.get("metadata"),
        "reactions": [{"name": r["name"], "users": r["users"]} for r in raw.get("reactions", [])],
        "event_id": event_id,
        "latest_reply": raw.get("latest_reply"),
    }


def to_message(raw: dict, channel: str, event_id: str | None = None):
    from pipe.core.contract import Message  # lazy: contract is a core module

    return Message(**message_fields(raw, channel, event_id))


def buttons_to_blocks(buttons) -> list | None:
    """Neutral buttons (`action_id`, `label`) to one Block Kit actions block."""
    if not buttons:
        return None
    els = [
        {
            "type": "button",
            "action_id": b.action_id,
            "text": {"type": "plain_text", "text": b.label},
        }
        for b in buttons
    ]
    return [{"type": "actions", "elements": els}]


def mention(handle: str) -> str:
    return f"<@{handle}>"


def escape_mentions(text: str) -> str:
    """Escape & < > so that untrusted text cannot make Slack links, mentions or broadcasts.

    Slack reads <...> as links and mentions. Escaping all three characters keeps
    <https://evil|https://good> as plain text. Call this on untrusted text BEFORE adding
    our own mention() syntax, so our mentions stay active.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
