"""bugfix: chat start, trigger start, failure stops the chain (US4)."""

from flow_kit import FlowRig, meta
from pipe.core.contract import RuntimeOutput


def test_chat_expand_has_five_steps_in_tag_order():
    r = FlowRig()
    r.say("<@UA> flow:bugfix login fails")
    steps = meta(r.plan())["pipeline"]["steps"]
    assert [s.get("capability") for s in steps][:4] == [
        "tag:reproduce", "tag:implement", "tag:e2e", "tag:review",
    ]  # fmt: skip
    assert steps[4]["agent"] == "human:U9" and steps[1]["access"] == "write"


def test_allowlisted_trigger_starts_with_no_check_and_no_button():
    r = FlowRig(allowlist=("BT",), trigger=True)
    r.trigger("<@UA> flow:bugfix issue 12: login fails")
    plans = r.task("B1", "plan")
    assert [meta(m)["status"] for m in plans] == ["needs_approval", "done"]
    assert "issue 12" in meta(plans[0])["pipeline"]["steps"][0]["goal"]
    assert not r.buttons()
    r.pump()
    assert r.calls() == 1  # reproduce runs; implement waits on the 004 gate
    assert [m for m in r.task() if meta(m).get("step") == 1][-1]


def test_trigger_not_on_the_allowlist_asks_the_owner():
    r = FlowRig(trigger=True)
    r.trigger("<@UA> flow:bugfix issue 12")
    (b,) = r.buttons()
    assert [x.action_id for x in b["buttons"]] == ["pipe_accept", "pipe_reject"]
    assert len(r.task("B1", "plan")) == 1 and r.calls() == 0


def test_reproduce_failed_stops_the_chain_with_retry():
    r = FlowRig()
    for rt in r.rt.values():
        rt.output = RuntimeOutput("no repro", "failed")
    r.say("<@UA> flow:bugfix x")
    r.react(r.plan())
    r.pump()
    last = r.task()[-1]
    assert (meta(last)["step"], meta(last)["status"]) == (0, "failed")
    assert not [m for m in r.task() if meta(m).get("step") == 1]
    assert [b.action_id for b in r.buttons()[-1]["buttons"]] == ["pipe_retry"]


def test_missing_reproduce_tag_is_named():
    offers = {k: ["implement", "e2e", "review"] for k in ("B1", "B2", "B3")}
    r = FlowRig(offers=offers)
    top = r.say("<@UA> flow:bugfix x")
    assert "flow bugfix: missing tags: reproduce" in r.texts(top)[-1]
