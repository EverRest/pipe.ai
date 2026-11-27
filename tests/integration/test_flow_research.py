"""research: research, then summarize; both read (US10)."""

from flow_kit import FlowRig, done, meta
from pipe.core.contract import RuntimeFailed

OFFERS = {"B1": ["research"], "B2": ["summarize"], "B3": []}


def test_links_reach_summarize_and_the_document_is_an_artifact():
    r = FlowRig(offers=OFFERS)
    r.rt["B1"].script = [done("found", artifacts=["https://web.example/p"])]
    r.rt["B2"].script = [done("doc", artifacts=["https://files.example/doc"])]
    r.say("<@UA> flow:research how does X scale")
    assert [s["access"] for s in r.plan_steps()] == ["read", "read"]
    r.react(r.plan())
    r.pump()
    assert r.rt["B2"].steps()[0].task["payload"]["artifacts"] == ["https://web.example/p"]
    assert meta(r.task()[-1])["artifacts"] == ["https://files.example/doc"]


def test_missing_research_tag_is_named():
    r = FlowRig(offers={"B1": ["summarize"], "B2": [], "B3": []})
    top = r.say("<@UA> flow:research x")
    assert "flow research: missing tags: research" in r.texts(top)[-1]


def test_timeout_fails_with_retry():
    r = FlowRig(offers=OFFERS)
    r.rt["B1"].script = [RuntimeFailed("timeout")]
    r.say("<@UA> flow:research x")
    r.react(r.plan())
    r.pump()
    assert meta(r.task()[-1])["reason"] == "timeout"
    assert [b.action_id for b in r.buttons()[-1]["buttons"]] == ["pipe_retry"]
