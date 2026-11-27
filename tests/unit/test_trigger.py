from types import SimpleNamespace as NS

from pipe.core.pipeline import Pipeline
from pipe.core.trigger import Trigger, decide_trigger, is_trigger_card, parse_trigger

CARDS = {"B1": {"kind": "trigger", "skills": [], "bot_user_id": "UB1"}, "B2": {"kind": "agent"}}
PIPE = {"steps": [{"agent": "any", "capability": "tag:review", "access": "read", "goal": "Review"}]}


def pay(**kw):
    p = {
        "v": 1,
        "phase": "plan",
        "status": "needs_approval",
        "by": "B1",
        "hop": 0,
        "pipeline": PIPE,
    }
    p.update(kw)
    return {k: v for k, v in p.items() if v is not None}


def msg(payload=None, text="<@UA> Nightly check", sender="B1", ts="1.1", thread_ts=None, **kw):
    kw = {"sender_handle": None, "sender_is_bot": True, **kw}
    return NS(sender_id=sender, ts=ts, thread_ts=thread_ts, payload=payload, text=text, **kw)


def test_form_a():
    t = parse_trigger(msg(pay()), CARDS, None)
    assert isinstance(t, Trigger)
    assert (t.ts, t.sender, t.flow, t.title) == ("1.1", "B1", None, "Nightly check")
    assert isinstance(t.pipeline, Pipeline) and t.pipeline.steps[0].capability == "tag:review"


def test_pipeline_source_not_trusted():
    p = pay(pipeline={**PIPE, "source": "flow:x"})
    assert parse_trigger(msg(p), CARDS, None).pipeline.source == "free"


def test_form_b():
    m = msg(pay(pipeline=None), text="<@UA> flow:nightly run it")
    t = parse_trigger(m, CARDS, "nightly")
    assert (t.flow, t.pipeline, t.title) == ("nightly", None, "run it")


def test_both_neither_empty_goal():
    assert parse_trigger(msg(pay()), CARDS, "nightly") is None
    assert parse_trigger(msg(pay(pipeline=None)), CARDS, None) is None
    assert (
        parse_trigger(msg(pay(pipeline=None), text="<@UA> flow:nightly "), CARDS, "nightly") is None
    )


def test_refused():
    bad = [
        msg(pay(), sender="B9"),  # no card
        msg(pay(by="B2"), sender="B2"),  # agent card
        msg(pay(by="B2")),
        msg(pay(hop=1)),
        msg(pay(v=2)),
        msg(pay(phase="step")),
        msg(pay(next={"agent": "B2"})),
        msg(pay(pipeline={"steps": "x"})),
        msg(pay(pipeline={})),
        msg(pay(), thread_ts="0.9"),
        msg(None),
        msg(pay(), sender_handle="UX"),
        msg(pay(), sender_is_bot=False),
    ]
    for m in bad:
        assert parse_trigger(m, CARDS, None) is None, m
    assert parse_trigger(msg(pay(), thread_ts="1.1"), CARDS, None)  # own ts is top-level


def test_title_clean_and_cut():
    m = msg(pay(), text="<@UA> hi <@U2> <!channel> <https://x|y> xoxb-12345678 " + "a" * 300)
    t = parse_trigger(m, CARDS, None).title
    assert "<" not in t and "xoxb" not in t and len(t) <= 200


def test_no_mutation():
    p, m = pay(), msg(pay())
    snap = repr(m.payload)
    parse_trigger(m, CARDS, None)
    assert repr(m.payload) == snap and p == pay()


def test_decide_trigger():
    assert decide_trigger("B1", ["B1"]) == ("allow", "allowlisted")
    for s in ("b1", "B1 ", None, ""):
        assert decide_trigger(s, ["B1"]) == ("ask", "not_allowlisted")
    assert decide_trigger("B1", []) == ("ask", "not_allowlisted")
    assert decide_trigger("U1", ["U1"]) == ("allow", "allowlisted")


def test_is_trigger_card():
    assert is_trigger_card({"kind": "trigger", "skills": []})
    assert not is_trigger_card({"kind": "trigger", "skills": [{"name": "x"}]})
    assert not is_trigger_card({"kind": "agent", "skills": []})
    assert not is_trigger_card(None)
