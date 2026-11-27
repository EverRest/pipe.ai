"""A trigger bot starts a pipeline through the planner adapter (FR-013 to FR-019)."""

import time

from delegation_kit import CH, Rig, meta
from pipe.core.contract import ClickEvent, MentionEvent, Message
from thread_kit import step

TRIG = {
    "bot_id": "BT", "bot_user_id": "UT", "owner": "OT", "name": "pipe-gitlab",
    "kind": "trigger", "skills": [],
    "description": "d", "mode": "ci", "hash": "h",
}  # fmt: skip
TWO = {"steps": [step("B1"), step("B2", "cap-2")]}
TEXT = "<@UA> Nightly check"


def rig(allow=("BT",), **kw):
    r = Rig()
    r.a.stepper.allowlist = tuple(allow)
    ts = r.ta._ts()
    md = {"event_type": "pipe.card.v1", "event_payload": TRIG}
    r.ta.messages.append(Message("CA", ts, ts, "BT", True, "card", "UT", md))
    return r


def trigger(r, pipeline=TWO, text=TEXT, sender="BT", ts=None, **p):
    pay = {"v": 1, "phase": "plan", "status": "needs_approval", "by": sender, "hop": 0, **p}
    if pipeline is not None:
        pay["pipeline"] = pipeline
    md = {"event_type": "pipe.task.v1", "event_payload": pay}
    ts = ts or r.ta._ts()
    handle = "UT" if sender == "BT" else None
    m = Message(CH, ts, ts, sender, True, text, handle, md)
    r.ta.messages.append(m)
    return m


def deliver(r, m, eid=None):
    ev = MentionEvent(CH, m.ts, m.thread, m.sender_id, True, m.text, eid or f"e{m.ts}")
    r.ta.raise_event(ev)
    return m


def task_msgs(r, by="B1"):
    return [m for m in r.ta.messages if m.metadata and meta(m).get("by") == by]


def plan_msgs(r):
    return [m for m in task_msgs(r) if meta(m)["phase"] == "plan"]


def pump(r):
    seen = 0
    for _ in range(10):
        new = [m for m in r.ta.messages[seen:] if m.metadata and meta(m).get("next")]
        seen = len(r.ta.messages)
        for m in new:
            for t in (r.ta, r.tb):
                t.raise_event(
                    MentionEvent(CH, m.ts, m.thread, m.sender_id, True, m.text, f"h{m.ts}")
                )
        if len(r.ta.messages) == seen:
            return


def final(r):
    return [meta(m)["status"] for m in r.ta.messages if "status" in meta(m)][-1]


def test_allowlisted_trigger_plans_starts_and_runs_to_done():
    r = rig()
    deliver(r, trigger(r))
    plan, start = plan_msgs(r)
    assert meta(plan)["status"] == "needs_approval" and meta(start)["status"] == "done"
    assert not [p for p in r.ta.posts if p["buttons"]] and not r.rt_a.inputs
    assert meta(plan)["pipeline"]["source"] == "free"
    pump(r)
    assert len(r.rt_a.inputs) == 1 and len(r.rt_b.inputs) == 1 and final(r) == "done"


def test_not_allowlisted_asks_the_owner_and_accept_runs_once():
    r = rig(allow=())
    deliver(r, trigger(r))
    (plan,) = plan_msgs(r)
    post = next(p for p in r.ta.posts if p["buttons"])
    assert [b.action_id for b in post["buttons"]] == ["pipe_accept", "pipe_reject"]
    assert "<@OA>" in post["text"] and "pipe-gitlab" in post["text"]
    click = lambda who, k: r.ta.raise_event(ClickEvent(k, CH, plan.ts, who, "pipe_accept"))  # noqa: E731
    click("OT", "k1")  # not the owner of the planner
    click("U9", "k2")
    assert len(plan_msgs(r)) == 1
    click("OA", "k3")
    click("OA", "k4")
    assert len(plan_msgs(r)) == 2  # one start only
    assert not r.ta.updates[-1]["buttons"]
    pump(r)
    assert final(r) == "done"


def test_reject_ends_the_plan_without_retry():
    r = rig(allow=())
    deliver(r, trigger(r))
    (plan,) = plan_msgs(r)
    r.ta.raise_event(ClickEvent("k1", CH, plan.ts, "OA", "pipe_reject"))
    u = r.ta.updates[-1]
    p = u["metadata"]["event_payload"]
    assert (p["status"], p["reason"]) == ("failed", "rejected") and not u["buttons"]
    assert "Reason: rejected" in u["text"]
    r.ta.raise_event(ClickEvent("k2", CH, plan.ts, "OA", "pipe_accept"))
    assert len(plan_msgs(r)) == 1 and not r.rt_a.inputs


def test_invalid_plan_is_a_failed_plan_message_with_no_button():
    r = rig()
    deliver(r, trigger(r, {"steps": [step("B1"), step("BT", "cap-1")]}))
    (plan,) = plan_msgs(r)
    assert meta(plan)["status"] == "failed" and "is a trigger bot" in plan.text
    assert not any(p["buttons"] for p in r.ta.posts)


def test_form_b_expands_the_flow_with_no_runtime_call():
    r = rig()
    r.a.flows = {"nightly": object()}
    r.a.expand = lambda name: {"steps": TWO["steps"], "source": "free"}
    text = "<@UA> flow:nightly run it"
    deliver(r, trigger(r, None, text))
    assert [meta(m)["status"] for m in plan_msgs(r)] == ["needs_approval", "done"]
    assert r.rt_a.inputs == []
    pump(r)
    assert final(r) == "done"


def test_unknown_flow_fails_the_plan_with_no_button():
    r = rig()
    deliver(r, trigger(r, None, "<@UA> flow:nope run it"))
    (plan,) = plan_msgs(r)
    assert meta(plan)["status"] == "failed"
    assert "could not build a plan (unknown flow)" in plan.text
    assert not any(p["buttons"] for p in r.ta.posts)


def test_both_forms_or_neither_start_nothing():
    r = rig()
    deliver(r, trigger(r, TWO, "<@UA> flow:nightly x"))
    deliver(r, trigger(r, None, TEXT))
    assert not plan_msgs(r)


def test_untrusted_triggers_start_nothing():
    r = rig()
    n = len(r.ta.posts)
    deliver(r, trigger(r, sender="B9"))  # no card
    deliver(r, trigger(r, sender="B2"))  # agent card
    deliver(r, trigger(r, hop=1))
    assert not plan_msgs(r) and len(r.ta.posts) == n


def test_same_event_twice_gives_one_plan():
    r = rig()
    m = trigger(r)
    deliver(r, m, "same")
    deliver(r, m, "same")
    assert len([x for x in plan_msgs(r) if meta(x)["status"] == "needs_approval"]) == 1


def test_trigger_posted_while_down_is_planned_after_start():
    r = rig()
    trigger(r, ts=f"{time.time():.6f}")
    r.a.wake_pass()
    assert len(plan_msgs(r)) == 2
    r.a.wake_pass()
    assert len(plan_msgs(r)) == 2


def test_write_step_of_a_trigger_pipeline_still_asks_the_step_owner():
    plan = {"steps": [step("B1"), {**step("B2", "cap-2"), "access": "write"}]}
    r = rig()
    deliver(r, trigger(r, plan))
    pump(r)
    gate = task_msgs(r, "B2")[-1]
    assert meta(gate)["status"] == "needs_approval" and not r.rt_b.inputs
    assert any(p["buttons"] for p in r.tb.posts + r.tb.updates if "buttons" in p)
