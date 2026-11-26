from pipe.core.contract import Message, SessionStatus
from pipe.core.status import (
    is_status_query,
    next_status,
    parse_status_messages,
    payload,
    recent,
    render,
    render_summary,
)

esc = lambda s: s.replace("<", "&lt;")  # noqa: E731
N = dict(session_id="s", who="w", repo="r", branch="b")


def test_transitions():
    s = next_status(None, "SessionStart", 100, **N)
    assert s.stage == "started" and s.blocker == "" and s.updated_at == 100
    s = next_status(s, "Stop", 200)
    assert s.stage == "idle"
    s = next_status(s, "SessionEnd", 300)
    assert s.stage == "stopped"
    s2 = next_status(s, "SessionStart", 400)
    assert s2.stage == "started" and s2.started_at == s.started_at
    assert next_status(None, "Stop", 1, **N).stage == "idle"
    assert next_status(None, "SessionEnd", 1, **N).stage == "stopped"


def test_updated_at_forward_only():
    s = next_status(None, "SessionStart", 100, **N)
    assert next_status(s, "Stop", 50).updated_at == 100


def test_render_and_payload_escape_scrub():
    s = SessionStatus("s", "w", "<!channel>", "xoxb-123-abc-def", "idle", "t", 5)
    assert render(s, esc) == "w | &lt;!channel> | [redacted] | idle | blocker: none"
    p = payload(s, esc)
    assert p["event_type"] == "pipe.status.v1"
    ep = p["event_payload"]
    assert ep["repo"] == "&lt;!channel>" and ep["updated_at"] == 5
    assert set(ep) == {
        "v",
        "session_id",
        "who",
        "repo",
        "branch",
        "stage",
        "blocker",
        "started_at",
        "updated_at",
    }


def pm(payload, bot=True, et="pipe.status.v1"):
    md = {"event_type": et, "event_payload": payload}
    return Message("C", "1.0", "1.0", "B", bot, "x", metadata=md)


GOOD = dict(
    v=1,
    session_id="s",
    who="w",
    repo="r",
    branch="b",
    stage="idle",
    blocker="",
    started_at="t",
    updated_at=5,
)


def test_parse_status_messages():
    assert len(parse_status_messages([pm(GOOD)])) == 1
    assert parse_status_messages([pm(GOOD, bot=False)]) == []
    assert parse_status_messages([pm(GOOD, et="other")]) == []
    assert parse_status_messages([pm({**GOOD, "stage": "dead"})]) == []
    assert parse_status_messages([pm({**GOOD, "repo": 3})]) == []
    assert parse_status_messages([pm({**GOOD, "updated_at": "5"})]) == []
    assert parse_status_messages([Message("C", "1", "1", "B", True, "x")]) == []


def test_recent():
    old = SessionStatus("a", "w", "r", "b", "idle", "t", 0)
    new = SessionStatus("b", "w", "r", "b", "idle", "t", 100000)
    assert recent([old, new], 100000 + 10) == [new]
    assert recent([old], 86400) == [old]


def test_summary():
    assert render_summary([]) == "No sessions in the last 24 hours."
    s = SessionStatus("s", "w", "<!here>", "b", "idle", "t", 5)
    assert render_summary([s], esc) == "w | &lt;!here> | b | idle | blocker: none"


def test_is_status_query():
    assert is_status_query("<@B> Who works on what?", "<@B>")
    assert is_status_query("<@B> tell me who works on what today", "<@B>")
    assert not is_status_query("<@B> hello", "<@B>")
