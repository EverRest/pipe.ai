"""Post, pin, and update the agent card in the agents channel."""

import logging
from dataclasses import asdict

from pipe.core.card import (
    CARD_EVENT,
    CardState,
    card_text,
    decide_publish,
    pick_own_card,
    validate_card,
)

log = logging.getLogger(__name__)
SCAN = 200  # newest top-level messages checked when state has no card


def _find_card(slack, channel, bot_id):
    msgs = [
        {"ts": m.ts, "channel": channel, "bot_id": m.sender_id, "metadata": m.metadata}
        for m in slack.history(channel, limit=SCAN)
    ]
    return pick_own_card(msgs, bot_id)


def sync_card(slack, state: dict, card, notices) -> dict:
    """Return the state values to save ({} on no change or on error). Never raises."""
    try:
        for n in notices:
            log.info("notice %s %s: %s", n.kind, n.id, n.text)
        if not card.owner:
            log.warning("card not posted: owner is empty")
            return {}
        if errs := validate_card(card):
            log.error("card not posted: %s", errs)
            return {}
        channel = state.get("agents_channel_id")
        if not channel:
            log.warning("card not posted: no agents channel")
            return {}
        saved = state.get("card")
        cur = CardState(**saved) if saved else _find_card(slack, channel, state.get("bot_id"))
        text = card_text(card, slack.escape_mentions)
        meta = {"event_type": CARD_EVENT, "event_payload": asdict(card)}
        action = decide_publish(card.hash, cur)
        ts = cur.ts if cur else None
        if action == "update":
            try:
                slack.update_message(channel, ts, text, metadata=meta)
            except Exception as e:
                if "message_not_found" not in str(e):
                    raise
                action = "post"  # a person deleted the card
        if action == "post":
            ts = slack.post_message(channel, text, metadata=meta)
        try:
            if ts not in slack.list_pins(channel):
                slack.pin(channel, ts)
        except Exception as e:
            log.error("card pin failed: %s", e)
        if action == "none" and saved:
            return {}
        return {"card": {"channel": channel, "ts": ts, "hash": card.hash}}
    except Exception as e:
        log.error("card sync failed: %s", e)
        return {}
