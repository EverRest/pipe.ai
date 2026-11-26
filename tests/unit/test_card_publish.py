from pipe.core.card import CardState, decide_publish, pick_own_card

CS = CardState("C1", "1.0", "h1")


def test_decide():
    assert decide_publish("h1", None) == "post"
    assert decide_publish("h2", CS) == "update"
    assert decide_publish("h1", CS) == "none"


def msg(ts, bot="B1", et="pipe.card.v1", h="h", payload_bot=None):
    return {
        "channel": "C1",
        "ts": ts,
        "bot_id": bot,
        "metadata": {"event_type": et, "event_payload": {"bot_id": payload_bot or bot, "hash": h}},
    }


def test_pick():
    ms = [
        msg("1.0", h="old"),
        msg("3.0", bot="B2"),
        msg("2.0", h="new"),
        msg("4.0", et="x"),
        msg("5.0", bot="B9", payload_bot="B1"),
        {"ts": "6.0"},
    ]
    assert pick_own_card(ms, "B1") == CardState("C1", "2.0", "new")
    assert pick_own_card(ms[1:2], "B1") is None
    assert pick_own_card([], "B1") is None
