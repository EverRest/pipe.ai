from pipe.core.catchup import parents_to_scan, pick_missed
from pipe.core.contract import Message


def msg(ts, text="<@B> hi", thread=None, sender="U1", latest=None):
    return Message("C", ts, thread or ts, sender, False, text, latest_reply=latest)


def test_parents_to_scan():
    old, upd, new = msg("1.0"), msg("2.0", latest="9.0"), msg("8.0")
    stale = msg("3.0", latest="4.0")
    assert parents_to_scan([old, upd, new, stale], "5.0") == [upd, new]


def test_pick_missed_basic_and_order():
    a, b = msg("8.0"), msg("6.0")
    assert pick_missed([a, b], "B", "5.0", set(), "<@B>") == [b, a]


def test_pick_missed_drops():
    assert pick_missed([msg("4.0")], "B", "5.0", set(), "<@B>") == []  # old
    assert pick_missed([msg("6.0")], "B", "5.0", {"C:6.0"}, "<@B>") == []  # handled
    assert pick_missed([msg("6.0", text="x")], "B", "5.0", set(), "<@B>") == []  # no mention
    assert pick_missed([msg("6.0", sender="B")], "B", "5.0", set(), "<@B>") == []  # self
    reply = msg("7.0", text="done", thread="6.0", sender="B")
    assert pick_missed([msg("6.0"), reply], "B", "5.0", set(), "<@B>") == []  # answered


def test_pick_missed_thread_reply_old_parent():
    r = msg("9.0", thread="1.0")
    assert pick_missed([msg("1.0", text="x"), r], "B", "5.0", set(), "<@B>") == [r]
