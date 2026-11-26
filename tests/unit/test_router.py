from pipe.core.contract import MentionEvent
from pipe.core.router import Decision, is_owner, should_handle

M = lambda h: f"<@{h}>"  # noqa: E731


def ev(**kw):
    d = dict(
        channel="C",
        ts="1.0",
        thread_ts="1.0",
        sender_id="U1",
        sender_is_bot=False,
        text="<@B> hi",
        event_id="E1",
    )
    return MentionEvent(**{**d, **kw})


def h(e, **kw):
    return should_handle(e, "B", M, **kw)


def test_reply():
    assert h(ev()) == Decision("reply", "mention")


def test_ignores():
    assert h(ev(sender_is_bot=True)).action == "ignore"
    assert h(ev(sender_id="B")).action == "ignore"
    assert h(ev(), event_ids=["E1"]).action == "ignore"
    assert h(ev(), in_flight={"E1"}).action == "ignore"
    assert h(ev(), mention_keys=["C:1.0"]).action == "ignore"
    assert h(ev(), in_flight={"C:1.0"}).action == "ignore"
    assert h(ev(text="no mention")).action == "ignore"


def test_catchup_event_without_id():
    assert h(ev(event_id=None)).action == "reply"


def test_status_query():
    assert h(ev(text="<@B> Who works on what?")).action == "status_query"
    assert h(ev(text="<@B> Who works on what?"), mention_keys=["C:1.0"]).action == "ignore"
    assert h(ev(text="<@B> Who works on what?", sender_is_bot=True)).action == "ignore"


def test_is_owner():
    assert is_owner("U1", "U1")
    assert not is_owner("U2", "U1")
    assert not is_owner("", "")
    assert not is_owner("U1", None)
