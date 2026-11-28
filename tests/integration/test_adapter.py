import time

from fakes import FakeRuntime, FakeTransport
from pipe import adapter, state
from pipe.config import Config
from pipe.core.contract import MentionEvent, RuntimeOutput
from pipe.core.scrub import scrub

CH = "C1"
TOKEN = "xoxb-123456789-abcdefgh"  # noqa: S105


def make(runtime=None, transport=None, owner="U_OWNER"):
    state.save_state(last_seen_ts="1699999999.000000")  # before the fake clock
    t = transport or FakeTransport(channels={"pipe-status": "C_STATUS", "gen": CH})
    r = runtime or FakeRuntime()
    cfg = Config("agent", "keychain:x", owner=owner)
    a = adapter.build(cfg, t, r, scrub, t.escape_mentions)
    a.start()
    return a, t, r


def ev(t, text="<@B1> hi", sender="U_OWNER", event_id="E1", **kw):
    m = t.add_message(CH, text, sender_id=sender, **kw)
    return MentionEvent(CH, m.ts, m.thread, sender, kw.get("sender_is_bot", False), text, event_id)


def test_mention_gets_one_reply_with_clean_input():
    a, t, r = make()
    e = ev(t)
    t.raise_event(e)
    posts = [p for p in t.posts if p["channel"] == CH]
    assert [(p["text"], p["thread"]) for p in posts] == [("ok", e.thread_ts)]
    inp = r.inputs[0]
    assert inp.requester_is_owner is True
    assert set(inp.task) == {"id", "purpose"} and inp.task["purpose"] == "chat"
    assert inp.thread == [{"user": "U_OWNER", "text": "<@B1> hi"}]


def test_non_owner_flag():
    a, t, r = make()
    t.raise_event(ev(t, sender="U_X"))
    assert r.inputs[0].requester_is_owner is False


def test_same_event_twice_one_reply():
    a, t, r = make()
    e = ev(t)
    t.raise_event(e)
    t.raise_event(e)
    assert len(r.inputs) == 1 and len(t.posts) == 1


def test_seen_key_survives_restart():
    a, t, r = make()
    e = ev(t)
    t.raise_event(e)
    a2, _, r2 = make(transport=t, runtime=FakeRuntime())
    t.raise_event(MentionEvent(CH, e.ts, e.thread_ts, "U_OWNER", False, e.text, "E2"))
    assert r2.inputs == [] and len(t.posts) == 1
    assert f"{CH}:{e.ts}" in state.load_seen()["mention_keys"]


def test_bot_messages_ignored():
    a, t, r = make()
    t.raise_event(ev(t, sender="B9", sender_is_bot=True, event_id="E2"))
    t.raise_event(ev(t, sender="B1", event_id="E3"))  # the agent itself
    assert r.inputs == [] and t.posts == []


def test_runtime_failure_posts_scrubbed_message_and_marks_seen():
    r = FakeRuntime(error=f"boom {TOKEN}")
    a, t, _ = make(runtime=r)
    e = ev(t)
    t.raise_event(e)
    assert len(t.posts) == 1
    text = t.posts[0]["text"]
    assert text.startswith("I could not finish this task. Reason: ") and TOKEN not in text
    assert f"{CH}:{e.ts}" in state.load_seen()["mention_keys"]


def test_reply_is_scrubbed_and_escaped():
    r = FakeRuntime(RuntimeOutput(text=f"<!channel> key {TOKEN}"))
    a, t, _ = make(runtime=r)
    t.raise_event(ev(t))
    text = t.posts[0]["text"]
    assert TOKEN not in text and "<!channel>" not in text and "&lt;!channel&gt;" in text


def test_catch_up_after_reconnect_answers_once():
    a, t, r = make()
    t.link_down = True
    m = t.add_message(CH, "<@U1> missed", sender_id="U_OWNER")  # U1 is the handle
    assert r.inputs == []
    t.reconnect()
    t.reconnect()
    assert len(r.inputs) == 1
    assert [p["thread"] for p in t.posts] == [m.thread]


def test_status_query_no_runtime():
    a, t, r = make()
    md = {
        "event_type": "pipe.status.v1",
        "event_payload": {
            "v": 1, "session_id": "s1", "who": "bob", "repo": "r", "branch": "b",
            "stage": "idle", "blocker": "", "started_at": "x", "updated_at": int(time.time()),
        },
    }  # fmt: skip
    t.add_message(
        "C_STATUS", "line", sender_id="B1", sender_is_bot=True, metadata=md, ts=f"{time.time():.6f}"
    )
    t.raise_event(ev(t, text="<@B1> who works on what?"))
    assert r.inputs == []
    assert "bob | r | b | idle" in t.posts[0]["text"]


def test_owner_tools_off_when_thread_has_other_person():
    a, t, r = make()
    p = t.add_message(CH, "context", sender_id="U_X")
    m = t.add_message(CH, "<@B1> hi", sender_id="U_OWNER", thread=p.ts)
    t.raise_event(MentionEvent(CH, m.ts, m.thread, "U_OWNER", False, m.text, "E9"))
    assert r.inputs[0].requester_is_owner is False


def test_owner_tools_off_when_thread_has_other_bot():
    a, t, r = make()
    p = t.add_message(CH, "note", sender_id="B_OTHER", sender_is_bot=True)
    m = t.add_message(CH, "<@B1> hi", sender_id="U_OWNER", thread=p.ts)
    t.raise_event(MentionEvent(CH, m.ts, m.thread, "U_OWNER", False, m.text, "E9"))
    assert r.inputs[0].requester_is_owner is False


def test_owner_tools_on_when_thread_is_owner_and_own_bot_only():
    a, t, r = make()
    p = t.add_message(CH, "note", sender_id=a.agent_id, sender_is_bot=True)
    m = t.add_message(CH, "<@B1> hi", sender_id="U_OWNER", thread=p.ts)
    t.raise_event(MentionEvent(CH, m.ts, m.thread, "U_OWNER", False, m.text, "E9"))
    assert a.agent_id and r.inputs[0].requester_is_owner is True
