from pipe import transport_slack_events as ev
from pipe.core.contract import ClickEvent, MentionEvent, ReactionEvent


class FakeApp:
    def __init__(self):
        self.h = {}

    def event(self, name):
        return lambda f: self.h.setdefault(name, f)

    def action(self, _pattern):
        return lambda f: self.h.setdefault("action", f)


def setup():
    app, got = FakeApp(), []
    ev.register_handlers(app, got.append)
    return app, got


def test_mention():
    app, got = setup()
    e = {"channel": "C1", "ts": "1.1", "user": "U2", "text": "<@U1> hi"}
    app.h["app_mention"](event=e, body={"event_id": "Ev9"})
    assert got == [MentionEvent("C1", "1.1", "1.1", "U2", False, "<@U1> hi", "Ev9")]


def test_mention_in_thread_and_bot():
    app, got = setup()
    e = {
        "channel": "C1",
        "ts": "2.2",
        "thread_ts": "1.1",
        "bot_id": "B3",
        "user": "U3",
        "text": "x",
    }
    app.h["app_mention"](event=e, body={"event_id": "Ev1"})
    assert (got[0].thread_ts, got[0].sender_id, got[0].sender_is_bot) == ("1.1", "B3", True)


def test_reaction():
    app, got = setup()
    e = {"user": "U2", "reaction": "eyes", "item": {"channel": "C1", "ts": "1.1"}}
    app.h["reaction_added"](event=e, body={"event_id": "Ev2"})
    assert got == [ReactionEvent("Ev2", "C1", "1.1", "U2", "eyes")]


def test_click_acks():
    app, got = setup()
    acked = []
    body = {
        "channel": {"id": "C1"},
        "message": {"ts": "1.1"},
        "user": {"id": "U2"},
        "actions": [{"action_id": "approve"}],
        "trigger_id": "T1",
    }
    app.h["action"](ack=lambda: acked.append(1), body=body)
    assert acked and got == [ClickEvent("T1", "C1", "1.1", "U2", "approve")]


def test_reconnect_on_hello_only():
    class Client:
        message_listeners = []

    c, calls = Client(), []
    ev.register_reconnect(c, lambda: calls.append(1))
    (listener,) = c.message_listeners
    listener(c, {"type": "events_api"}, "")
    listener(c, {"type": "hello"}, "")
    assert calls == [1]


def test_click_reads_thread_ts_from_message_or_container():
    app, got = setup()
    base = {
        "channel": {"id": "C1"},
        "user": {"id": "U2"},
        "actions": [{"action_id": "approve"}],
        "trigger_id": "T1",
    }
    app.h["action"](ack=lambda: None, body={**base, "message": {"ts": "2.2", "thread_ts": "1.1"}})
    app.h["action"](
        ack=lambda: None, body={**base, "message": {"ts": "3.3"}, "container": {"thread_ts": "1.1"}}
    )
    assert [c.thread_ts for c in got] == ["1.1", "1.1"]
