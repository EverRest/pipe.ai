"""troubleshoot: collect, diagnose, implement (US6)."""

from flow_kit import FlowRig, done, meta
from pipe.core.context import MAX_CONTEXT_TEXT
from pipe.core.contract import RuntimeFailed

LINK = "https://files.example/logs"
OFFERS = {"B1": ["collect"], "B2": ["diagnose"], "B3": ["implement"]}


def rig(**kw):
    return FlowRig(offers=OFFERS, **kw)


def test_alert_trigger_starts_with_no_check():
    r = rig(allowlist=("BT",), trigger=True)
    r.trigger("<@UA> flow:troubleshoot pod crash loop")
    assert [meta(m)["status"] for m in r.task("B1", "plan")] == ["needs_approval", "done"]
    assert not r.buttons()


def test_artifacts_and_context_reach_diagnose_and_big_text_is_cut():
    r = rig()
    r.rt["B1"].script = [done("x" * 50_000, artifacts=[LINK])]
    r.say("<@UA> flow:troubleshoot pods restart")
    r.react(r.plan())
    r.pump()
    pay = r.rt["B2"].steps()[0].task["payload"]
    assert pay["artifacts"] == [LINK]
    assert len(pay["context"][0]["text"]) <= MAX_CONTEXT_TEXT


def test_no_data_makes_diagnose_fail_with_a_reason():
    r = rig()
    r.rt["B1"].script = [done("no data")]
    r.rt["B2"].script = [RuntimeFailed("no data to diagnose")]
    r.say("<@UA> flow:troubleshoot x")
    r.react(r.plan())
    r.pump()
    last = r.task()[-1]
    assert (meta(last)["step"], meta(last)["status"]) == (1, "failed")
    assert meta(last)["reason"] == "no data to diagnose"
    assert not [m for m in r.task() if meta(m).get("step") == 2]


def test_implement_for_another_owner_meets_the_gate():
    r = rig()
    r.say("<@UA> flow:troubleshoot x")
    r.react(r.plan())
    r.pump()
    last = r.task()[-1]
    assert (meta(last)["by"], meta(last)["step"], meta(last)["status"]) == (
        "B3",
        2,
        "needs_approval",
    )
    assert r.buttons() and not r.rt["B3"].inputs
