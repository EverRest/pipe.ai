"""nightly: a scheduled check; run_failed branches, a timeout does not (US12; DQ5, DQ8)."""

from flow_kit import FlowRig, done, meta
from pipe.core.contract import RuntimeFailed, RuntimeOutput

OFFERS = {"B1": ["e2e", "deps-check"], "B2": ["troubleshoot"], "B3": []}


def test_allowlisted_trigger_starts_with_the_default_tag_and_no_goal():
    r = FlowRig(offers=OFFERS, allowlist=("BT",), trigger=True)
    r.trigger("<@UA> flow:nightly")
    assert meta(r.plan())["pipeline"]["steps"][0]["capability"] == "tag:e2e"
    assert [meta(m)["status"] for m in r.task("B1", "plan")] == ["needs_approval", "done"]
    assert not r.buttons()


def test_param_picks_the_tag_and_a_bad_value_is_refused():
    r = FlowRig(offers=OFFERS, allowlist=("BT",), trigger=True)
    r.trigger("<@UA> flow:nightly check=deps-check")
    assert meta(r.plan())["pipeline"]["steps"][0]["capability"] == "tag:deps-check"
    r.trigger("<@UA> flow:nightly check=lint")
    bad = r.task("B1", "plan")[-1]
    assert meta(bad)["status"] == "failed" and "flow nightly: bad value for check" in bad.text


def test_failed_check_branches_and_the_report_is_kept():
    r = FlowRig(offers=OFFERS, allowlist=("BT",), trigger=True)
    r.rt["B1"].script = [RuntimeOutput("2 failed", "failed")]
    r.rt["B2"].script = [done("cause")]
    r.trigger("<@UA> flow:nightly")
    r.pump()
    assert len(r.rt["B2"].steps()) == 1 and r.final() == "done"


def test_timeout_does_not_branch():
    r = FlowRig(offers=OFFERS, allowlist=("BT",), trigger=True)
    r.rt["B1"].script = [RuntimeFailed("timeout")]
    r.trigger("<@UA> flow:nightly")
    r.pump()
    assert not r.rt["B2"].steps() and meta(r.task()[-1])["reason"] == "timeout"


def test_trigger_not_allowlisted_asks_the_owner_and_a_repeat_starts_a_second_thread():
    r = FlowRig(offers=OFFERS, trigger=True)
    r.trigger("<@UA> flow:nightly")
    r.trigger("<@UA> flow:nightly")
    assert len(r.buttons()) == 2 and len({m.thread for m in r.task("B1", "plan")}) == 2
