"""Trust in senders and cards. Pure. Thread text is untrusted."""

from pipe.core.card import validate_card
from pipe.core.claim import ts_key

CARD_EVENT = "pipe.card.v1"


def owner_thread(messages, self_id: str, owner: str | None) -> bool:
    """True only for a non-empty owner and every sender being `self_id` or `owner`."""
    return bool(owner and all(m.sender_id in (self_id, owner) for m in messages))


def trusted_cards(messages) -> dict[str, dict]:
    """bot_id -> card payload. Keeps only cards a bot posted about itself.
    One bot, two cards: the latest wins. One bot_user_id on two cards: the lowest ts keeps it."""
    best: dict[str, tuple] = {}  # bot_id -> (ts_key, payload)
    for m in messages:
        meta = m.metadata or {}
        p = meta.get("event_payload")
        if not (m.sender_is_bot and meta.get("event_type") == CARD_EVENT and isinstance(p, dict)):
            continue
        if p.get("bot_id") != m.sender_id or not p.get("bot_user_id"):
            continue
        if m.sender_handle is not None and m.sender_handle != p["bot_user_id"]:
            continue
        if validate_card(p):
            continue
        k = ts_key(m.ts)
        if m.sender_id not in best or k > best[m.sender_id][0]:
            best[m.sender_id] = (k, p)
    # first card message of a bot_user_id wins; use the lowest ts among each bot's kept card
    owner: dict[str, tuple] = {}
    for bot, (k, p) in best.items():
        u = p["bot_user_id"]
        if u not in owner or (k, bot) < owner[u][:2]:
            owner[u] = (k, bot)
    return {bot: p for bot, (k, p) in best.items() if owner[p["bot_user_id"]][1] == bot}


def trusted_sender(msg, cards: dict) -> bool:
    """A bot that has a card; `sender_handle` (when present) equals the card bot_user_id."""
    c = cards.get(msg.sender_id)
    if not (msg.sender_is_bot and c):
        return False
    return msg.sender_handle is None or msg.sender_handle == c["bot_user_id"]


def hop_refused(hop: int, limit: int) -> bool:
    return hop > limit
