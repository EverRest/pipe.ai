from pipe.cards import CardCache
from pipe.core.contract import Message


def card(bot, user, name="a", ts="1.0", sender=None, handle="same", **kw):
    p = {
        "name": name,
        "description": "d",
        "owner": "UO",
        "bot_id": bot,
        "bot_user_id": user,
        "kind": "agent",
        "mode": "laptop",
        "skills": [],
        "hash": "h",
    }
    p.update(kw)
    return Message(
        "CA",
        ts,
        ts,
        sender or bot,
        True,
        "card",
        sender_handle=user if handle == "same" else handle,
        metadata={"event_type": "pipe.card.v1", "event_payload": p},
    )


class Reader:
    def __init__(self, msgs):
        self.msgs, self.n = msgs, 0

    def history(self, channel, oldest=None, limit=None):
        self.n += 1
        return self.msgs


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def make(msgs):
    r, c = Reader(msgs), Clock()
    return r, c, CardCache(r, "CA", clock=c)


def test_ttl():
    r, c, cc = make([card("B1", "U1")])
    assert set(cc.cards()) == {"B1"}
    c.t = 299
    cc.cards()
    assert r.n == 1
    c.t = 301
    cc.cards()
    assert r.n == 2


def test_unknown_sender_refresh_once_per_minute():
    r, c, cc = make([card("B1", "U1")])
    cc.cards()
    cc.note_sender("BX")
    assert r.n == 2
    c.t = 30
    cc.note_sender("BX")
    assert r.n == 2
    c.t = 61
    cc.note_sender("BX")
    assert r.n == 3
    cc.note_sender("B1")
    assert r.n == 3


def test_agent_users_no_read_and_no_card_bot_absent():
    r, c, cc = make([card("B1", "U1")])
    cc.cards()
    n = r.n
    assert cc.agent_users() == {"U1": "B1"}
    assert r.n == n


def test_trust_rules():
    msgs = [
        card("B1", "U1", ts="1.0"),
        card("B2", "U2", sender="B9"),  # author is not the card bot
        card("B3", "U3", handle="U7"),  # handle mismatch
        card("B4", "U1", ts="2.0"),  # duplicate bot_user_id, later ts
        card("B5", "U5", name="see https://x.io/y"),  # invalid card
        card("B6", "U6", description="ok"),
    ]
    msgs[5] = Message("CA", "6.0", "6.0", "B6", False, "x", metadata=msgs[5].metadata)  # human
    _, _, cc = make(msgs)
    assert set(cc.cards()) == {"B1"}


def test_newest_card_per_bot_wins():
    _, _, cc = make(
        [card("B1", "U1", ts="1.0", name="old"), card("B1", "U1", ts="2.0", name="new")]
    )
    assert cc.cards()["B1"]["name"] == "new"


def test_duplicate_bot_user_id_keeps_lower_ts():
    r, c, cc = make([card("B1", "U1", ts="5.0"), card("B2", "U1", ts="3.0")])
    assert set(cc.cards()) == {"B2"}
