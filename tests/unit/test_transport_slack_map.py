import ast
import re
from pathlib import Path
from types import SimpleNamespace

from pipe import transport_slack_map as m


def raw(**kw):
    base = {"ts": "1700000000.000100", "user": "U1", "text": "hi"}
    return {**base, **kw}


def test_bot_message_identity():
    f = m.message_fields(raw(bot_id="B1", user="U9"), "C1")
    assert (f["sender_id"], f["sender_is_bot"], f["sender_handle"]) == ("B1", True, "U9")


def test_user_message_identity():
    f = m.message_fields(raw(), "C1")
    assert (f["sender_id"], f["sender_is_bot"], f["sender_handle"]) == ("U1", False, "U1")


def test_event_id_and_catch_up():
    assert m.message_fields(raw(), "C1", event_id="Ev1")["event_id"] == "Ev1"
    assert m.message_fields(raw(), "C1")["event_id"] is None


def test_ts_thread_channel_text():
    f = m.message_fields(raw(), "C1")
    assert (f["channel"], f["ts"], f["thread"], f["text"]) == (
        "C1",
        "1700000000.000100",
        "1700000000.000100",
        "hi",
    )
    assert m.message_fields(raw(thread_ts="1699.000001"), "C1")["thread"] == "1699.000001"


def test_metadata_and_reactions():
    md = {"event_type": "pipe_status", "event_payload": {"v": 1}}
    rx = [{"name": "x", "users": ["U2"], "count": 1}]
    f = m.message_fields(raw(metadata=md, reactions=rx), "C1")
    assert f["metadata"] == md
    assert f["reactions"] == [{"name": "x", "users": ["U2"]}]
    g = m.message_fields(raw(), "C1")
    assert g["metadata"] is None and g["reactions"] == []


def test_buttons_to_blocks():
    b = [SimpleNamespace(action_id="a1", label="Go"), SimpleNamespace(action_id="a2", label="No")]
    blocks = m.buttons_to_blocks(b)
    assert len(blocks) == 1 and blocks[0]["type"] == "actions"
    els = blocks[0]["elements"]
    assert [(e["action_id"], e["text"]["text"]) for e in els] == [("a1", "Go"), ("a2", "No")]
    assert all(e["type"] == "button" and e["text"]["type"] == "plain_text" for e in els)


def test_no_buttons_no_block():
    assert m.buttons_to_blocks(None) is None
    assert m.buttons_to_blocks([]) is None


def test_mention():
    assert m.mention("U1") == "<@U1>"


def test_escape_mentions():
    for s in ["<!channel>", "<!here>", "<!everyone>", "<@U123>", "<!subteam^S1>"]:
        out = m.escape_mentions(f"a {s} b")
        assert "<!" not in out and "<@" not in out
    assert m.escape_mentions("plain text, a < b") == "plain text, a &lt; b"


def test_id_pattern():
    for ok in ["B012ABCDEF", "U034GHIJKL", "W1AB"]:
        assert re.match(m.id_pattern, ok)
    for bad in ["pavlo", "b012"]:
        assert not re.match(m.id_pattern, bad)


def test_no_slack_library_import():
    tree = ast.parse(Path(m.__file__).read_text())
    names = [
        n.module if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for a in getattr(n, "names", [])
    ]
    assert not [x for x in names if x and x.startswith("slack")]


def test_to_message_real_type():
    from pipe.core.contract import Message

    msg = m.to_message(raw(bot_id="B1", user="U9"), "C1", event_id="Ev1")
    assert isinstance(msg, Message)
    assert (msg.channel, msg.sender_id, msg.sender_is_bot, msg.event_id) == (
        "C1",
        "B1",
        True,
        "Ev1",
    )


def test_latest_reply_mapped():
    assert m.message_fields(raw(latest_reply="2.0"), "C1")["latest_reply"] == "2.0"


def test_escape_mentions_blocks_disguised_link():
    from pipe.transport_slack_map import escape_mentions

    evil = "<https://evil.example|https://good.example>"
    assert escape_mentions(evil) == "&lt;https://evil.example|https://good.example&gt;"


def test_escape_mentions_escapes_ampersand_and_keeps_plain_text():
    from pipe.transport_slack_map import escape_mentions

    assert escape_mentions("a & b") == "a &amp; b"
    assert escape_mentions("hello world") == "hello world"


def test_mention_after_escape_stays_active():
    from pipe.transport_slack_map import escape_mentions, mention

    text = escape_mentions("<!channel> hi") + " " + mention("U1")
    assert text == "&lt;!channel&gt; hi <@U1>"
