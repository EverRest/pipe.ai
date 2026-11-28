"""Cache of the other agents' cards from `#pipe-agents` (the trust source). Read-only."""

import time

from pipe.core.trust import trusted_cards

TTL = 300
MISS_GAP = 60


class CardCache:
    def __init__(self, reader, channel, clock=time.monotonic):
        self.reader, self.channel, self.clock = reader, channel, clock
        self._cards, self._at, self._miss = {}, None, None

    def refresh(self):
        self._cards = trusted_cards(self.reader.history(self.channel))
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
