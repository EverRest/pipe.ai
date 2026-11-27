"""test-run: a failed run branches to troubleshoot; a timeout does not (DQ5)."""

from flow_kit import FlowRig, done, meta
from pipe.core.contract import RuntimeFailed, RuntimeOutput

LINK = "https://files.example/report"


def run(first, then=None):
    r = FlowRig(offers={"B1": ["e2e"], "B2": ["troubleshoot"], "B3": []})
    r.rt["B1"].script = [first]
    r.rt["B2"].script = [then] if then else []
    top = r.say("<@UA> flow:test-run the login suite")
    r.react(r.plan())
    r.pump()
    return r, top


def steps_done(r, i):
    return [m for m in r.task() if meta(m).get("step") == i]


def test_success_ends_done_and_never_starts_troubleshoot():
    r, _ = run(done("all green", artifacts=[LINK]))
    assert meta(r.task()[-1])["artifacts"] == [LINK] and r.final() == "done"
    assert not steps_done(r, 1) and r.calls() == 1


def test_run_failed_branches_once_and_the_flow_ends_after_it():
    r, _ = run(RuntimeOutput("2 tests failed", "failed"), done("cause: x"))
    e2e = steps_done(r, 0)[-1]
    assert (meta(e2e)["status"], meta(e2e)["reason"]) == ("failed", "run_failed")
    assert not [u for u in r.buttons() if u["ts"] == e2e.ts]  # no Retry on a branched step
    assert len(r.rt["B1"].steps()) == 1 and len(r.rt["B2"].steps()) == 1 and r.final() == "done"
    assert meta(r.task()[-1])["step"] == 1


def test_timeout_does_not_branch_and_offers_retry():
    r, _ = run(RuntimeFailed("timeout"))
    assert not steps_done(r, 1)
    assert meta(r.task()[-1])["reason"] == "timeout"
    assert [b.action_id for b in r.buttons()[-1]["buttons"]] == ["pipe_retry"]


def test_no_claimer_does_not_branch():
    r = FlowRig()
    top = r.say("<@UA> flow:test-run x")
    r.react(r.plan())  # no pump: nobody sees the handoff
    r.a["B1"].stepper.check_unclaimed(top.ts, 0, 1, "C")
    last = r.task()[-1]
    assert (meta(last)["status"], meta(last)["reason"]) == ("failed", "no_claimer")
    assert not steps_done(r, 1) and "next" not in meta(last)


def test_troubleshoot_failure_gives_retry_and_no_further_step():
    r, _ = run(RuntimeOutput("bad", "failed"), RuntimeFailed("boom"))
    last = r.task()[-1]
    assert (meta(last)["step"], meta(last)["status"]) == (1, "failed")
    assert [b.action_id for b in r.buttons()[-1]["buttons"]] == ["pipe_retry"]
