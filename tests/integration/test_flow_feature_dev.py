"""feature-dev end to end: gate, exclusion, hop 4, approval (SC-003, SC-007, SC-008)."""

from flow_kit import FlowRig, done, meta

PROP = {"steps": [{"agent": "B1", "access": "read", "goal": "x", "capability": "review-B1"}]}
LINK = "https://files.example/report"


def statuses(r, by, step):
    return [meta(m)["status"] for m in r.task(by) if meta(m).get("step") == step]


def test_whole_flow_with_gate_exclusion_and_hop_4():
    r = FlowRig()
    r.rt["B1"].script = [done("tasks", proposal=PROP)]
    r.rt["B1"].output = done("report", artifacts=[LINK])
    r.say("<@UA> flow:feature-dev add export")
    r.react(r.plan())
    r.pump()
    assert statuses(r, "B1", 0)[-1] == "needs_approval" and r.calls() == 1  # held at the gate
    assert not [m for m in r.task() if meta(m).get("step") == 1]
    r.react(r.task("B1")[-1])  # the starter releases the gate
    r.pump()
    gate = r.task("B1")[-1]
    assert meta(gate)["step"] == 1 and meta(gate)["status"] == "needs_approval"  # 004 gate
    assert r.buttons()[-1]["buttons"]
    r.click(gate, "OA", "pipe_accept")
    r.pump()
    e2e = next(m for m in r.task("B1") if meta(m).get("step") == 2 and meta(m).get("artifacts"))
    assert meta(e2e)["artifacts"] == [LINK]
    review = [m for m in r.task() if meta(m).get("step") == 3 and meta(m)["status"] == "done"]
    assert meta(review[-1])["by"] != "B1"  # the claimant of implement cannot review
    assert max(meta(m)["hop"] for m in r.task()) == 4
    last = r.task()[-1]
    assert meta(last)["status"] == "needs_approval" and "Approve the result" in last.text
    assert not [m for m in r.task() if meta(m)["status"] == "failed"]
    r.click(last, "U9", "pipe_approve")
    assert meta(r.task()[-1])["status"] == "done"


def test_one_agent_for_review_and_implement_is_rejected_before_check():
    offers = {"B1": ["decompose", "implement", "e2e", "review"], "B2": ["decompose"], "B3": []}
    r = FlowRig(offers=offers)
    top = r.say("<@UA> flow:feature-dev x")
    assert not r.task(phase="plan")
    assert "no agent can claim after exclusion" in r.texts(top)[-1]


def test_review_with_no_other_agent_ends_no_claimer():
    offers = {"B1": ["decompose", "implement", "e2e", "review"], "B2": ["implement"], "B3": []}
    r = FlowRig(offers=offers)
    top = r.say("<@UA> flow:feature-dev x")
    r.rt["B1"].script = [done("t", proposal=PROP)]
    r.react(r.plan())
    r.pump()
    r.react(r.task("B1")[-1])
    r.pump()
    r.click(r.task("B1")[-1], "OA", "pipe_accept")
    r.pump()
    assert not [m for m in r.task() if meta(m).get("step") == 3]
    r.a["B1"].stepper.check_unclaimed(top.ts, 3, 4, "C")
    last = r.task()[-1]
    assert (meta(last)["status"], meta(last)["reason"]) == ("failed", "no_claimer")
