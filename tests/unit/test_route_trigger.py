"""route: trigger mentions, Accept/Reject on a trigger plan, Wake (FR-014 to FR-018)."""

import copy

from pipe.core.contract import ClickEvent, Message
from pipe.core.route import BotMessage, ThreadState, Wake, route, wake_all
from pipe.core.trigger import Trigger
from thread_kit import CARDS, TOP, USERS, plan_msg, start_msg

TRIG = {
    "bot_id": "BT", "bot_user_id": "UT", "owner": "OT", "name": "pipe-gitlab",
    "kind": "trigger", "skills": [],
}  # fmt: skip
STEP = {"agent": "any", "capability": "tag:review", "access": "read", "goal": "Review"}
PAY = {
    "v": 1, "phase": "plan", "status": "needs_approval", "by": "BT", "hop": 0,
    "pipeline": {"steps": [STEP]},
}  # fmt: skip
TEXT = "<@UA> Nightly"


def pay(**kw):
    p = copy.deepcopy(PAY)
    p.update(kw)
    return {k: v for k, v in p.items() if v is not None}


def tstate(msgs=(), me="B1", text=TEXT, payload=None, sender="BT", **kw):
    md = {"event_type": "pipe.task.v1", "event_payload": payload or pay()}
    handle = TRIG["bot_user_id"] if sender == "BT" else None
    parent = Message("C", TOP, TOP, sender, True, text, handle, md)
    cards = {**CARDS, "BT": TRIG}
    return ThreadState(
        "C", TOP, sender, text, (parent, *msgs), cards, {**USERS, "UT": "BT"},
        me, CARDS[me]["bot_user_id"], **kw,
    )  # fmt: skip


def top(payload=None, text=TEXT, sender="BT", **kw):
    return BotMessage("C", TOP, TOP, sender, payload or pay(), "UT", text=text, **kw)


def act(ev, st):
    d = route(ev, st)
    return d.action, d.reason


def test_valid_trigger_gives_trigger():
    d = route(top(), tstate())
    assert d.action == "trigger" and isinstance(d.arg, Trigger)
    assert (d.arg.ts, d.arg.sender, d.arg.flow) == (TOP, "BT", None)


def test_form_b_gives_the_flow_name():
    text = "<@UA> flow:nightly run it"
    d = route(top(pay(pipeline=None), text), tstate(text=text, payload=pay(pipeline=None)))
    assert d.action == "trigger" and d.arg.flow == "nightly" and d.arg.pipeline is None


def test_both_forms_or_neither_is_bad_payload():
    both = "<@UA> flow:nightly run it"
    assert act(top(pay(), both), tstate(text=both)) == ("ignore", "bad_payload")
    p = pay(pipeline=None)
    assert act(top(p), tstate(payload=p)) == ("ignore", "bad_payload")


def test_other_agent_first_is_not_planner():
    text = "<@UB> Nightly"
    assert act(top(text=text), tstate(text=text)) == ("ignore", "not_planner")


def test_no_card_and_agent_card_start_nothing():
    st = tstate(sender="B9")
    assert act(top(sender="B9"), st) == ("ignore", "no_card")
    ev = BotMessage("C", TOP, TOP, "B2", pay(by="B2"), "UB", text=TEXT)
    assert act(ev, tstate(sender="B2")) == ("ignore", "not_trigger")


def test_trigger_with_next_is_not_an_agent():
    p = pay(next={"agent": "B1", "access": "read", "payload": {"step": 0}})
    assert act(top(p), tstate(payload=p)) == ("ignore", "trigger_not_agent")


def test_hop_1_and_planned_thread_start_nothing():
    assert route(top(pay(hop=1)), tstate()).reason == "bad_payload"
    planned = tstate([plan_msg()])
    assert act(top(), planned) == ("ignore", "already_planned")
    busy = tstate(in_flight=frozenset({f"trigger:C:{TOP}"}))
    assert act(top(), busy)[0] == "ignore"


def click(who, action="pipe_accept"):
    return ClickEvent("E", "C", plan_msg().ts, who, action)


def test_accept_by_the_planner_owner_only():
    st = tstate([plan_msg()])
    assert act(click("OA"), st) == ("start", "")
    for who in ("BT", "OT", "U9", "OB"):  # starter, trigger owner, others
        assert route(click(who), st).action == "ignore"


def test_reject_and_second_click():
    st = tstate([plan_msg()])
    assert act(click("OA", "pipe_reject"), st) == ("reject_plan", "")
    assert route(click("OA"), tstate([plan_msg(), start_msg()])).action == "ignore"
    rejected = plan_msg(status="failed", reason="rejected")
    assert route(click("OA"), tstate([rejected])).action == "ignore"
    assert route(click("OA", "pipe_retry"), tstate([rejected])).action == "ignore"


def test_chat_thread_plan_click_keeps_003_rules():
    from thread_kit import state

    st = state([plan_msg()])
    assert act(click("OA"), st) == ("ignore", "not_pending")


def test_wake_gives_trigger_once_and_no_plan_flow():
    text = "<@UA> flow:nightly go"
    p = pay(pipeline=None)
    st = tstate(text=text, payload=p)
    ds = wake_all(Wake(TOP, 1.0), st)
    assert [d.action for d in ds] == ["trigger"] and ds[0].arg.flow == "nightly"
    assert wake_all(Wake(TOP, 1.0), tstate([plan_msg()], text=text, payload=p)) == []
