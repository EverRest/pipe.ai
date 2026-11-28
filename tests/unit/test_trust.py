from pipe.core.contract import Message
from pipe.core.trust import hop_refused, owner_thread, trusted_cards, trusted_sender


def card(bot_id, user, name="n"):
    return {
        "name": name,
        "description": "d",
        "owner": "U1",
        "bot_id": bot_id,
        "bot_user_id": user,
        "kind": "agent",
        "mode": "laptop",
        "skills": [],
        "hash": "h",
    }


def msg(ts, sender, payload, bot=True, handle=None, event="pipe.card.v1"):
    meta = {"event_type": event, "event_payload": payload}
    return Message("C", ts, ts, sender, bot, "", handle, meta)


def test_trusted_cards_basic_drops():
    ok = msg("1.000001", "B1", card("B1", "UB1"), handle="UB1")
    cards = trusted_cards(
        [
            ok,
            msg("2.000001", "B2", card("B2", "UB2"), bot=False),  # person
            msg("3.000001", "B3", card("BX", "UB3")),  # bot_id != sender
            msg("4.000001", "B4", card("B4", "UB4"), handle="UOTHER"),  # handle mismatch
            msg("5.000001", "B5", card("B5", "")),  # no bot_user_id
            msg("6.000001", "B6", {**card("B6", "UB6"), "name": "see http://x.io/a"}),
            msg("7.000001", "B7", card("B7", "UB7"), event="other"),
        ]
    )
    assert set(cards) == {"B1"}


def test_no_handle_kept():
    assert set(trusted_cards([msg("1.000001", "B1", card("B1", "UB1"))])) == {"B1"}


def test_duplicate_user_lower_ts_keeps_any_order():
    a = msg("1.000001", "B1", card("B1", "UX"))
    b = msg("2.000001", "B2", card("B2", "UX"))
    assert set(trusted_cards([a, b])) == {"B1"}
    assert set(trusted_cards([b, a])) == {"B1"}


def test_one_bot_two_cards_highest_ts():
    a = msg("1.000001", "B1", card("B1", "U1x", "old"))
    b = msg("9.000001", "B1", card("B1", "U1x", "new"))
    assert trusted_cards([a, b])["B1"]["name"] == "new"
    assert trusted_cards([b, a])["B1"]["name"] == "new"


def test_trusted_sender():
    cards = trusted_cards([msg("1.000001", "B1", card("B1", "UB1"))])
    assert trusted_sender(msg("2.000001", "B1", {}, handle="UB1"), cards)
    assert trusted_sender(msg("2.000001", "B1", {}), cards)  # no handle
    assert not trusted_sender(msg("2.000001", "B1", {}, handle="UZ"), cards)
    assert not trusted_sender(msg("2.000001", "B9", {}), cards)
    assert not trusted_sender(msg("2.000001", "B1", {}, bot=False), cards)


def test_hop_refused():
    assert not hop_refused(3, 3)
    assert hop_refused(4, 3)
    assert not hop_refused(5, 5)
    assert hop_refused(6, 5)


def test_owner_thread():
    def m(*ids):
        return [Message("C", "1", "1", i, False, "") for i in ids]

    assert owner_thread(m("O", "ME"), "ME", "O")
    assert owner_thread(m("ME"), "ME", "O")
    assert not owner_thread(m("O", "BOT"), "ME", "O")
    assert not owner_thread(m("O", "H"), "ME", "O")
    assert not owner_thread(m("ME"), "ME", "")
    assert not owner_thread(m("ME"), "ME", None)
