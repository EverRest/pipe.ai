"""review-handoff: review, implement, re-review by another agent (US7)."""

from flow_kit import FlowRig, done, meta

DRAFTS = "https://files.example/drafts"


def test_drafts_reach_implement_and_the_implementer_cannot_re_review():
    r = FlowRig(offers={"B1": ["review"], "B2": ["implement"], "B3": ["review"]})
    r.rt["B1"].script = [done("drafts", artifacts=[DRAFTS])]
    r.say("<@UA> flow:review-handoff https://gitlab.example/mr/1")
    steps = meta(r.plan())["pipeline"]["steps"]
    assert "https://gitlab.example/mr/1" in steps[0]["goal"] and steps[2]["exclude_agents_of"] == [
        1
    ]
    r.react(r.plan())
    r.pump()
    gate = r.task("B2")[-1]
    assert meta(gate)["status"] == "needs_approval"  # write step, another owner
    r.click(gate, "OB", "pipe_accept")
    r.pump()
    assert r.rt["B2"].steps()[0].task["payload"]["artifacts"] == [DRAFTS]
    assert [meta(m)["by"] for m in r.task() if meta(m).get("step") == 2][-1] in ("B1", "B3")
    assert r.final() == "needs_approval" and "Approve" in r.task()[-1].text


def test_a_single_reviewer_may_review_again_when_it_did_not_implement():
    r = FlowRig(offers={"B1": ["review"], "B2": ["implement"], "B3": []})
    r.say("<@UA> flow:review-handoff mr")
    r.react(r.plan())
    r.pump()
    r.click(r.task("B2")[-1], "OB", "pipe_accept")
    r.pump()
    done_by = [
        meta(m)["by"] for m in r.task() if meta(m).get("step") == 2 and meta(m)["status"] == "done"
    ]
    assert done_by and set(done_by) == {"B1"}  # A, B, A is allowed


def test_trigger_with_an_mr_link_in_the_goal():
    r = FlowRig(allowlist=("BT",), trigger=True)
    r.trigger("<@UA> flow:review-handoff mr-77")
    assert "mr-77" in meta(r.plan())["pipeline"]["steps"][0]["goal"]
