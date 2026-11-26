"""Contract tests for Transport. Slack runs on a stub WebClient."""

import pytest

from fakes import FakeTransport
from pipe.core.contract import Button, ClickEvent, MentionEvent


def _fake():
    return FakeTransport()


def _slack():
    from unit.test_transport_slack import make_slack

    return make_slack()


@pytest.fixture(params=[_fake, _slack], ids=["fake", "slack"])
def t(request):
    return request.param()


def test_post_and_replies(t):
    root = t.post_message("C1", "root")
    ts = t.post_message("C1", "hi", thread=root, metadata={"event_type": "x", "event_payload": {}})
    got = [m for m in t.replies("C1", root) if m.ts == ts]
    assert got and got[0].thread == root and got[0].metadata["event_type"] == "x"
    assert got[0].reactions == []


def test_update_and_delete(t):
    ts = t.post_message("C1", "old", buttons=[Button("a", "A")])
    t.update_message("C1", ts, "new")
    assert [m.text for m in t.history("C1") if m.ts == ts] == ["new"]
    t.delete_message("C1", ts)
    assert all(m.ts != ts for m in t.history("C1"))


def test_history_each_message_once(t):
    for i in range(120):
        t.post_message("C1", str(i))
    ts = [m.ts for m in t.history("C1")]
    assert len(ts) == len(set(ts)) == 120


def test_pins(t):
    ts = t.post_message("C1", "card")
    t.pin("C1", ts)
    assert t.list_pins("C1") == [ts]


def test_send_dm_returns_none(t):
    assert t.send_dm("U2", "hello") is None


def test_events_and_reconnect(t):
    seen, calls = [], []
    t.on_event(seen.append)
    t.on_reconnect(lambda: calls.append(1))
    ev = MentionEvent("C1", "1.1", "1.1", "U2", False, "x")
    t.raise_event(ev)
    t.reconnect()
    assert seen == [ev] and calls == [1]
    assert not isinstance(seen[0], ClickEvent)


def test_upload_bytes_returns_https_link(t):
    root = t.post_message("C1", "root")
    link = t.upload_file("C1", root, "shot.png", b"png", "Shot")
    assert link.startswith("https://")
