"""Plan source and hop limit: 5 only for a template verified on this machine (DQ1, DQ10)."""

from dataclasses import replace
from types import SimpleNamespace as NS

from flow_kit import CH, FlowRig, meta
from pipe.core.contract import MentionEvent
from pipe.core.flows import expand
from pipe.core.route import card_view
from pipe.core.source import effective_source
from thread_kit import TOP, claim, handoff, plan_msg, start_msg

UNVERIFIED = "plan source not verified"


def seed(r, mutate=None):
    """A bugfix plan from B1 and a handoff of its last agent step at hop 4. Gives the handoff."""
    cards = card_view({k: c.metadata["event_payload"] for k, c in _cards(r).items()})
    plan = expand(r.flows["bugfix"], "g", starter="U9", cards=cards)
    steps = mutate(plan["steps"]) if mutate else plan["steps"]
    r.t["B1"].add_message(CH, "<@UA> flow:bugfix g", sender_id="U9", ts=TOP)
    h = handoff(9, "B1", "any", 3, 2, 4, text="<@UB> Step 4")
    r.t["B1"].messages.extend(
        [plan_msg(plan={"steps": steps, "source": plan["source"]}), start_msg()]
        + [claim(3 + i, "B1", i, "done") for i in range(3)]
        + [h]
    )
    return h


def _cards(r):
    return {m.sender_id: m for m in r.t["B1"].messages if m.channel == "CA" and m.metadata}


def deliver(r, h, to="B2"):
    r.t[to].raise_event(MentionEvent(CH, h.ts, h.thread, "B1", True, h.text, "EH"))
    return [m for m in r.task(to) if meta(m)["step"] == 3]


def test_verified_template_runs_at_hop_4_and_an_unverified_copy_refuses():
    r = FlowRig()
    out = deliver(r, seed(r))
    assert out and meta(out[-1])["status"] != "failed" and r.rt["B2"].steps()
    r = FlowRig()
    r.a["B2"].flows = {}  # no flows/ directory on the receiver
    out = deliver(r, seed(r))
    assert meta(out[-1])["status"] == "failed" and not r.rt["B2"].inputs
    assert UNVERIFIED in r.t["B2"].posts[-1]["text"]


def test_receiver_with_a_changed_copy_refuses():
    r = FlowRig()
    f = r.flows["bugfix"]
    r.a["B2"].flows = {"bugfix": replace(f, hash="0" * 32)}
    out = deliver(r, seed(r))
    assert meta(out[-1])["status"] == "failed" and UNVERIFIED in r.t["B2"].posts[-1]["text"]


def test_forged_steps_under_a_template_source_refuse_at_hop_4():
    r = FlowRig()
    out = deliver(r, seed(r, lambda st: [*st[:4], dict(st[3]), *st[4:]]))  # one more step
    assert meta(out[-1])["status"] == "failed" and not r.rt["B2"].inputs
    assert UNVERIFIED in r.t["B2"].posts[-1]["text"]


def test_a_goal_change_keeps_the_template_and_a_step_change_gives_free():
    r = FlowRig()
    cards = card_view({k: c.metadata["event_payload"] for k, c in _cards(r).items()})
    p = expand(r.flows["bugfix"], "g", starter="U9", cards=cards)
    steps = [dict(s) for s in p["steps"]]
    steps[0]["goal"] = "another goal text"
    mk = lambda st: NS(steps=st, source=p["source"])  # noqa: E731
    assert effective_source(mk(steps), r.flows, cards, "U9") == "template"
    steps[1]["access"] = "read"
    assert effective_source(mk(steps), r.flows, cards, "U9") == "free"
