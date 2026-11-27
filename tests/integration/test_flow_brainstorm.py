"""brainstorm: context, dialog, summary; no write step (US9)."""

from flow_kit import FlowRig, done, meta
from pipe.core.contract import RuntimeOutput

OFFERS = {"B1": ["context"], "B2": ["brainstorm"], "B3": ["summarize"]}
DOC = "https://files.example/summary"


def test_context_links_reach_the_dialog_and_the_summary_gets_both_texts():
    r = FlowRig(offers=OFFERS)
    r.rt["B1"].script = [done("found docs", artifacts=["https://docs.example/a"])]
    r.rt["B2"].script = [
        RuntimeOutput("Which goal?", "waiting", reason="needs_input"),
        done("we chose x"),
    ]
    r.rt["B3"].script = [done("summary", artifacts=[DOC])]
    top = r.say("<@UA> flow:brainstorm cache strategy")
    assert all(s["access"] == "read" for s in r.plan_steps())
    r.react(r.plan())
    r.pump()
    assert r.rt["B2"].steps()[0].task["payload"]["artifacts"] == ["https://docs.example/a"]
    r.reply(top, "<@UB> latency", sender="U9")
    r.pump()
    ctx = r.rt["B3"].steps()[0].task["payload"]["context"]
    assert [c["text"] for c in ctx] == ["found docs", "we chose x"]
    assert meta(r.task()[-1])["artifacts"] == [DOC] and r.final() == "done"
    assert not r.buttons()  # no write step, the 004 gate never asks


def test_no_context_found_still_starts_the_dialog():
    r = FlowRig(offers=OFFERS)
    r.rt["B1"].script = [done("no context found")]
    r.rt["B2"].script = [RuntimeOutput("Which goal?", "waiting", reason="needs_input")]
    r.say("<@UA> flow:brainstorm x")
    r.react(r.plan())
    r.pump()
    assert meta(r.task()[-1])["status"] == "waiting"
