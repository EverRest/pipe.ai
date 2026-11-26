"""send_summary with FakeTransport and a state dict (T042)."""

import re

from fakes import FakeTransport
from pipe.core.capability import Capability, Notice
from pipe.core.summary import build_summary
from pipe.owner_summary import send_summary

CAPS = [Capability("skill:a", "a", open=True)]


def start(tr, st, notices=(), owner="U123", exposed=()):
    s = build_summary(CAPS, exposed, list(notices))
    st.update(send_summary(tr, st, owner, s))


def test_first_start_one_dm_ten_starts_one_dm():
    tr, st = FakeTransport(), {}
    for _ in range(10):
        start(tr, st)
    assert len(tr.dms) == 1 and tr.dms[0][0] == "U123" and st["summary_hash"]


def test_new_notice_sends_again():
    tr, st = FakeTransport(), {}
    start(tr, st)
    start(tr, st, [Notice("unknown_id", "skill:zz", "not found")])
    assert len(tr.dms) == 2 and "unknown_id" in tr.dms[1][1]


def test_failed_dm_keeps_hash_unsaved_then_retries():
    tr, st = FakeTransport(), {}
    real = tr.send_dm

    def boom(*a):
        raise OSError("down")

    tr.send_dm = boom
    start(tr, st)
    assert "summary_hash" not in st
    tr.send_dm = real
    start(tr, st)
    assert len(tr.dms) == 1


def test_empty_owner_no_dm():
    tr, st = FakeTransport(), {}
    start(tr, st, owner="")
    assert not tr.dms and not st


def test_text_clean_and_mentions_escaped():
    tr, st = FakeTransport(), {}
    start(tr, st, [Notice("unknown_id", "x", "<!channel> <@U9>")])
    text = tr.dms[0][1]
    assert "<!" not in text and "<@" not in text
    assert not re.search(r"http|xox|/Users|~/", text)
