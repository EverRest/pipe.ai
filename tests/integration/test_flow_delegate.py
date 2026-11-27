"""delegate: a second agent mention fills $agent (US11; DQ9)."""

from flow_kit import FlowRig, done, meta

MR = "https://gitlab.example/mr/9"


def make(**kw):
    r = FlowRig(**kw)
    top = r.say("<@UA> <@UB> flow:delegate add a flag")
    r.react(r.plan())
    r.pump()
    return r, top


def test_plan_has_the_fixed_write_step_for_the_second_agent():
    r = FlowRig()
    r.say("<@UA> <@UB> flow:delegate add a flag")
    (s,) = r.plan_steps()
    assert (s["agent"], s["access"], s["capability"]) == ("B2", "write", "implement-B2")
    assert "add a flag" in s["goal"]


def test_gate_asks_when_the_sender_is_not_allowlisted():
    r, _ = make()
    last = r.task()[-1]
    assert (meta(last)["by"], meta(last)["status"]) == ("B2", "needs_approval")
    assert r.buttons() and not r.rt["B2"].inputs


def test_gate_allows_when_both_conditions_hold():
    r = FlowRig(allowlist=("B1", "U9"))
    r.rt["B2"].script = [done("mr", artifacts=[MR])]
    r.say("<@UA> <@UB> flow:delegate add a flag")
    r.react(r.plan())
    r.pump()
    assert len(r.rt["B2"].steps()) == 1 and not r.buttons()
    assert meta(r.task()[-1])["artifacts"] == [MR] and r.final() == "done"


def test_card_without_the_tag_and_extra_mentions_are_refused():
    r = FlowRig(offers={"B1": ["review"], "B2": ["review"], "B3": ["implement"]})
    top = r.say("<@UA> <@UB> flow:delegate x")
    assert "flow delegate: missing tags: implement" in r.texts(top)[-1]
    top = r.say("<@UA> <@UB> <@UC> flow:bugfix x")
    assert "takes no agent mention" in r.texts(top)[-1]
