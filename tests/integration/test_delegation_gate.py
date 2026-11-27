"""Owner gate in the step flow (spec 004 US2): button, accept, reject, idempotence."""

from delegation_kit import Rig, meta
from thread_kit import step

GATE_TEXT = (
    "Step 2 of 2 (write, agent-b): needs approval. <@OB> Accept or reject this work from agent-a."
)


def test_stranger_write_step_waits_for_the_owner():
    r = Rig()
    r.handoff(r.seed())
    g = r.gate()
    p = meta(g)
    assert (p["status"], p["access"], p["by"], p["step"], p["hop"]) == (
        "needs_approval", "write", "B2", 1, 2,
    )  # fmt: skip
    assert g.text == GATE_TEXT
    buttons = r.tb.updates[-1]["buttons"]
    assert [b.action_id for b in buttons] == ["pipe_accept", "pipe_reject"]
    assert r.rt_b.inputs == []  # nothing ran


def test_accept_runs_the_step_once():
    r = Rig()
    r.handoff(r.seed())
    g = r.gate()
    r.click(g, "OB")
    assert meta(r.gate())["status"] == "done"
    assert [i.request.access for i in r.rt_b.inputs] == ["write"]
    assert r.rt_b.inputs[0].requester_is_owner is False
    r.click(g, "OB", eid="K2")  # second click
    r.click(g, "OB", "pipe_reject", eid="K3")
    assert len(r.rt_b.inputs) == 1 and meta(r.gate())["status"] == "done"


def test_reject_fails_the_step_with_no_run_and_no_retry():
    r = Rig()
    r.handoff(r.seed())
    g = r.gate()
    r.click(g, "OB", "pipe_reject")
    p = meta(r.gate())
    assert (p["status"], p["reason"]) == ("failed", "rejected")
    assert r.tb.updates[-1]["buttons"] is None
    r.click(g, "OB", eid="K2")  # accept after reject
    assert r.rt_b.inputs == [] and meta(r.gate())["status"] == "failed"


def test_click_from_anyone_but_the_owner_is_ignored():
    r = Rig()
    r.handoff(r.seed())
    g, n = r.gate(), len(r.tb.updates)
    for i, who in enumerate(("U9", "OA", "B1", "UX")):  # starter, sender owner, bot, stranger
        r.click(g, who, eid=f"K{i}")
        r.click(g, who, "pipe_reject", eid=f"J{i}")
    assert len(r.tb.updates) == n and r.rt_b.inputs == []
    assert meta(r.gate())["status"] == "needs_approval"


def test_click_still_works_after_a_restart():
    r = Rig()
    r.handoff(r.seed())
    g = r.gate()
    r.restart_b()
    r.click(g, "OB")
    assert len(r.rt_b.inputs) == 1 and meta(r.gate())["status"] == "done"


def test_read_step_from_a_stranger_has_no_gate():
    r = Rig()
    plan = {"steps": [step("B1"), step("B2", "cap-2")], "source": "free"}
    r.handoff(r.seed(plan=plan, access="read"))
    assert meta(r.gate())["status"] == "done" and len(r.rt_b.inputs) == 1


def test_owner_started_thread_has_no_gate():
    r = Rig()
    r.handoff(r.seed(starter="OB"))
    assert meta(r.gate())["status"] == "done"
    assert r.rt_b.inputs[0].request.access == "write"


def test_one_bot_one_gate_and_no_hop_added():
    r = Rig()
    h = r.seed()
    r.handoff(h)
    r.handoff(h, eid="E2")  # same handoff again
    assert len(r.step_msgs()) == 1 and meta(r.gate())["hop"] == 2
