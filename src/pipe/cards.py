"""Cache of the other agents' cards from `#pipe-agents` (the trust source). Read-only."""

import time

from pipe.core.card import CARD_EVENT, validate_card

TTL = 300
MISS_GAP = 60


def _trusted(messages):
    """Cards posted by their own bot (D3). Newest per bot; lower ts wins a duplicate user."""
    best = {}
    for m in messages:
        meta = m.metadata or {}
        p = meta.get("event_payload")
        if not (m.sender_is_bot and meta.get("event_type") == CARD_EVENT and isinstance(p, dict)):
            continue
        if m.sender_id != p.get("bot_id") or validate_card(p):
            continue
        if m.sender_handle not in (None, p["bot_user_id"]):
            continue
        if m.sender_id not in best or float(m.ts) > float(best[m.sender_id][0]):
            best[m.sender_id] = (m.ts, p)
    owner = {}
    for _, p in sorted(best.values(), key=lambda x: float(x[0])):
        owner.setdefault(p["bot_user_id"], p["bot_id"])
    return {p["bot_id"]: p for _, p in best.values() if owner[p["bot_user_id"]] == p["bot_id"]}


class CardCache:
    def __init__(self, reader, channel, clock=time.monotonic):
        self.reader, self.channel, self.clock = reader, channel, clock
        self._cards, self._at, self._miss = {}, None, None

    def refresh(self):
        self._cards = _trusted(self.reader.history(self.channel))
        self._at = self.clock()

    def cards(self):
        """`{bot_id: card dict}`. Reads Slack at first use and after 5 minutes."""
        if self._at is None or self.clock() - self._at >= TTL:
            self.refresh()
        return self._cards

    def note_sender(self, sender_id):
        """Refresh once when a sender has no card; at most once per 60 seconds."""
        if sender_id in self.cards():
            return
        now = self.clock()
        if self._miss is None or now - self._miss >= MISS_GAP:
            self._miss = now
            self.refresh()

    def agent_users(self):
        """`{bot_user_id: bot_id}` from memory. No Slack call."""
        return {p["bot_user_id"]: b for b, p in self._cards.items()}
