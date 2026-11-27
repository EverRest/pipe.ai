"""planning: dialog, spec, decompose with a proposal (US8; DQ6, DQ7, DQ12)."""

from flow_kit import FlowRig, done, meta
from pipe.core.contract import RuntimeOutput

OFFERS = {"B1": ["brainstorm"], "B2": ["spec"], "B3": ["decompose"]}
ASK = RuntimeOutput("Which users?", "waiting", reason="needs_input")
PROP = {"steps": [{"agent": "B1", "access": "read", "goal": "x", "capability": "brainstorm-B1"}]}


def start(r, accept=False):
    top = r.say("<@UA> flow:planning an export feature")
    r.react(r.plan())
    r.pump()
    while accept and (g := r.task()[-1]) and meta(g)["status"] == "needs_approval" and r.buttons():
        r.click(g, "OA", "pipe_accept")
        r.pump()
        accept = (
            meta(r.task()[-1])["status"] == "needs_approval" and meta(r.task()[-1])["step"] == 1
        )
    return top


def waiting(r):
    return [m for m in r.task("B1") if meta(m)["status"] == "waiting"][-1]


def test_dialog_resumes_on_the_same_step_for_the_starter_only():
    r = FlowRig(offers=OFFERS)
    r.rt["B1"].script = [ASK, done("agreed")]
    top = start(r)
    q = waiting(r)
    r.reply(top, "<@UA> admins", sender="U8")  # not the starter, not the owner
    assert len(r.rt["B1"].steps()) == 1
    r.reply(top, "admins only", sender="U9")  # no mention of the agent
    assert len(r.rt["B1"].steps()) == 1
    r.reply(top, "<@UA> admins only", sender="U9")
    r.pump()
    assert len(r.rt["B1"].steps()) == 2
    mine = [
        meta(m) for m in r.task("B1", "step") if meta(m)["step"] == 0 and not meta(m).get("next")
    ]
    hops = {p["hop"] for p in mine}
    assert hops == {meta(q)["hop"]}  # same step, no new claim, no new hop


def test_dialog_timeout_fails_with_retry():
    r = FlowRig(offers=OFFERS)
    r.rt["B1"].script = [ASK]
    top = start(r)
    q = waiting(r)
    r.a["B1"].stepper.expire_dialog(top.ts, q.ts, "C")
    last = r.task()[-1]
    assert (meta(last)["status"], meta(last)["reason"]) == ("failed", "dialog_timeout")
    assert [b.action_id for b in r.buttons()[-1]["buttons"]] == ["pipe_retry"]


def test_spec_is_a_write_step_and_meets_the_gate():
    r = FlowRig(offers=OFFERS)
    r.rt["B1"].script = [done("agreed")]
    start(r)
    last = r.task()[-1]
    assert (meta(last)["by"], meta(last)["step"], meta(last)["status"]) == (
        "B2",
        1,
        "needs_approval",
    )


def test_bad_proposal_fails_the_step_and_a_good_one_is_context_only():
    r = FlowRig(offers={"B1": ["brainstorm", "spec"], "B2": [], "B3": ["decompose"]})
    r.rt["B3"].script = [done("t", proposal={"steps": [{"agent": "nobody"}]})]
    start(r, accept=True)
    last = r.task()[-1]
    assert (meta(last)["step"], meta(last)["reason"]) == (2, "invalid_proposal")
    r = FlowRig(offers={"B1": ["brainstorm", "spec"], "B2": [], "B3": ["decompose"]})
    r.rt["B3"].script = [done("t", proposal=PROP)]
    start(r, accept=True)
    gate = r.task("B3")[-1]
    assert meta(gate)["status"] == "needs_approval"
    before = meta(r.plan())["pipeline"]
    r.react(gate)
    r.pump()
    assert meta(r.task()[-1])["status"] == "done"  # the flow ends, no work starts
    assert meta(r.plan())["pipeline"] == before and len(r.plan_steps()) == 3
