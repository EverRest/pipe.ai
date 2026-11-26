"""Slack Transport over a stub WebClient. No network."""

import pytest

from pipe.core.contract import Button, UploadRefused
from pipe.state import pipe_home
from pipe.transport_slack import SlackTransport


class StubClient:
    """Records calls. Keeps messages per channel in ts order (oldest first)."""

    def __init__(self):
        self.msgs: dict[str, list[dict]] = {}
        self.pins: dict[str, list[str]] = {}
        self.calls: list[tuple] = []
        self.n = 0

    def _page(self, items, cursor, limit):
        start = int(cursor or 0)
        end = start + min(limit, 100)
        nxt = str(end) if end < len(items) else ""
        return {"ok": True, "messages": items[start:end], "response_metadata": {"next_cursor": nxt}}

    def auth_test(self):
        return {"bot_id": "B1", "user_id": "U1"}

    def conversations_list(self, cursor=None, limit=100, **kw):
        self.calls.append(("conversations_list", kw))
        chans = [{"id": f"C{i}", "name": f"ch{i}"} for i in range(250)]
        r = self._page(chans, cursor, limit)
        return {"channels": r["messages"], "response_metadata": r["response_metadata"]}

    def users_conversations(self, cursor=None, limit=100, **kw):
        r = self._page([{"id": "C1"}, {"id": "C2"}], cursor, limit)
        return {"channels": r["messages"], "response_metadata": r["response_metadata"]}

    def chat_postMessage(self, channel, text, thread_ts=None, metadata=None, blocks=None, **kw):
        self.calls.append(("chat_postMessage", channel, text, thread_ts, blocks))
        self.n += 1
        m = {"ts": f"1700000000.{self.n:06d}", "text": text, "bot_id": "B1", "user": "U1"}
        if thread_ts:
            m["thread_ts"] = thread_ts
        if metadata:
            m["metadata"] = metadata
        self.msgs.setdefault(channel, []).append(m)
        return {"ok": True, "ts": m["ts"]}

    def chat_update(self, channel, ts, text, metadata=None, blocks=None):
        for m in self.msgs[channel]:
            if m["ts"] == ts:
                m["text"] = text
                m["metadata"] = metadata or m.get("metadata")

    def chat_delete(self, channel, ts):
        self.msgs[channel] = [m for m in self.msgs[channel] if m["ts"] != ts]

    def conversations_history(self, channel, cursor=None, limit=100, oldest=None, **kw):
        top = [m for m in self.msgs.get(channel, []) if "thread_ts" not in m]
        if oldest:
            top = [m for m in top if float(m["ts"]) > float(oldest)]
        r = self._page(top[::-1], cursor, limit)  # newest first
        self.calls.append(("conversations_history", limit, kw))
        return r

    def conversations_replies(self, channel, ts, cursor=None, limit=100, oldest=None, **kw):
        thr = [m for m in self.msgs.get(channel, []) if m["ts"] == ts or m.get("thread_ts") == ts]
        if oldest:
            thr = [m for m in thr if float(m["ts"]) > float(oldest)]
        return self._page(thr, cursor, limit)  # oldest first

    def pins_add(self, channel, timestamp):
        self.pins.setdefault(channel, []).append(timestamp)

    def pins_list(self, channel):
        return {"items": [{"message": {"ts": t}} for t in self.pins.get(channel, [])]}

    def conversations_open(self, users):
        self.calls.append(("conversations_open", users))
        return {"channel": {"id": "D1"}}

    def files_upload_v2(self, **kw):
        self.calls.append(("files_upload_v2", kw))
        return {"file": {"permalink": "https://files.slack.com/f/1"}}


def make_slack(roots=None):
    """SlackTransport on a stub, with the contract-test hooks."""
    client = StubClient()
    t = SlackTransport(client, roots=roots, scrub=lambda s: s.replace("xoxb-secret", "[redacted]"))
    t.raise_event = t._emit
    t.reconnect = t._reconnected
    t.client = client
    return t


@pytest.fixture
def t():
    return make_slack()


def test_whoami_and_channels(t):
    assert (t.whoami().agent_id, t.whoami().handle) == ("B1", "U1")
    assert t.find_channel("ch220") == "C220"  # needs the second and third page
    with pytest.raises(KeyError):
        t.find_channel("nope")
    assert t.member_channels() == ["C1", "C2"]


def test_history_oldest_first_limit_keeps_newest(t):
    for i in range(5):
        t.post_message("C1", str(i))
    assert [m.text for m in t.history("C1")] == ["0", "1", "2", "3", "4"]
    assert [m.text for m in t.history("C1", limit=2)] == ["3", "4"]
    oldest = t.history("C1")[1].ts
    assert [m.text for m in t.history("C1", oldest=oldest)] == ["2", "3", "4"]


def test_history_pages_by_cursor(t):
    for i in range(230):
        t.post_message("C1", str(i))
    got = t.history("C1")
    assert len({m.ts for m in got}) == 230
    assert [c[1] for c in t.client.calls if c[0] == "conversations_history"] == [100, 100, 100]
    assert [m.text for m in t.history("C1", limit=150)][-1] == "229"
    assert len(t.history("C1", limit=150)) == 150


def test_replies_many(t):
    root = t.post_message("C1", "root")
    for i in range(130):
        t.post_message("C1", str(i), thread=root)
    assert len(t.replies("C1", root)) == 131


def test_buttons_become_blocks(t):
    t.post_message("C1", "x", buttons=[Button("a", "A")])
    assert t.client.calls[-1][4][0]["type"] == "actions"


def test_send_dm_opens_then_posts(t):
    assert t.send_dm("U2", "hi") is None
    assert ("conversations_open", "U2") in t.client.calls
    assert t.client.calls[-1][:3] == ("chat_postMessage", "D1", "hi")


def test_upload_bytes_and_scrub(t):
    link = t.upload_file("C1", "1.1", "xoxb-secret.png", b"png", "T xoxb-secret")
    calls = [c for c in t.client.calls if c[0] == "files_upload_v2"]
    assert link.startswith("https://") and len(calls) == 1
    kw = calls[0][1]
    assert (kw["channel"], kw["thread_ts"]) == ("C1", "1.1")
    assert kw["filename"] == "[redacted].png" and kw["title"] == "T [redacted]"


def test_upload_path_checks_roots(t, tmp_path):
    run = pipe_home() / "run"
    run.mkdir(parents=True)
    ok = run / "a.png"
    ok.write_bytes(b"x")
    assert t.upload_file("C1", "1.1", "a.png", ok, "A").startswith("https://")
    out = tmp_path / "b.png"
    out.write_bytes(b"x")
    link = run / "link.png"
    link.symlink_to(ok)
    for bad in (out, link, run, run / "big.png"):
        if bad.name == "big.png":
            bad.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
        with pytest.raises(UploadRefused):
            t.upload_file("C1", "1.1", "n", bad, "t")
    assert len([c for c in t.client.calls if c[0] == "files_upload_v2"]) == 1


def test_escape_then_mention(t):
    text = t.mention("U2") + " " + t.escape_mentions("<!channel>")
    assert text == "<@U2> &lt;!channel&gt;"
