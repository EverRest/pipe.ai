"""Pure core path: route -> stepper over shared fake threads. No Slack, no claude."""

from fakes import FakeRuntime, FakeTransport
from pipe.core.capability import Capability
from pipe.core.contract import ClickEvent, ReactionEvent, RuntimeOutput
from pipe.core.route import BotMessage, route
from pipe.stepper import Stepper
from thread_kit import CARDS, PARENT, TOP, claim, handoff, human, plan_msg, start_msg, state, step


class Agent:
    def __init__(self, me, shared, caps):
        self.me = me
        self.ft = FakeTransport(me, CARDS[me]["bot_user_id"], {"pipe-work": "C"})
        self.ft.messages = shared.messages  # one thread for all agents
        self.ft._ts = shared._ts
        self.rt = FakeRuntime(RuntimeOutput(f"result of {me}"))
        self.st = Stepper(self.ft, self.rt, self.load, caps, sleep=lambda s: None)
        self.seen = 0

    def load(self, channel=None, thread=None):
        return state(tuple(m for m in self.ft.messages if m.thread == TOP), me=self.me)

    def handle(self, ev):
        d = route(ev, self.load())
        if d.action == "claim":
            self.st.run_step(*d.arg)
        elif d.action == "start":
            self.st.start_pipeline(self.load(), d.arg)
        elif d.action == "refuse":
            self.st.refuse(d.arg, d.reason)
        elif d.action == "approve":
            self.st.approve_step(d.arg)
        return d


def world(plan, me=("B1", "B2", "B3"), caps=None):
    shared = FakeTransport("B0", "U0", {"pipe-work": "C"})
    shared._n = 100
    shared.add_message("C", PARENT, "U9", ts=TOP)
    shared.messages.append(plan_msg(plan=plan))
    caps = caps or {c: Capability(c, c, tags=("review",)) for c in ("cap-1", "cap-2", "cap-3")}
    return shared, {m: Agent(m, shared, caps) for m in me}


def pump(agents, shared, limit=10):
    """Deliver every new task message with `next` to every agent, until the thread is quiet."""
    done = 0
    for _ in range(limit):
        new = [m for m in shared.messages[done:] if m.metadata]
        done = len(shared.messages)
        for m in new:
            p = m.metadata["event_payload"]
            if p.get("next"):
                ev = BotMessage("C", m.ts, TOP, m.sender_id, p, m.sender_handle)
                for a in agents.values():
                    a.handle(ev)
        if len(shared.messages) == done:
            return


def statuses(shared):
    return [m.metadata["event_payload"]["status"] for m in shared.messages if m.metadata]


def test_full_pipeline_with_human_approval():
    plan = {"steps": [step("B1"), step("B2", "cap-2"), human("U9")], "source": "free"}
    shared, ag = world(plan)
    plan_ts = shared.messages[1].ts
    d = ag["B1"].handle(ReactionEvent("e", "C", plan_ts, "U9", "white_check_mark"))
    assert d.action == "start"
    assert (
        ag["B2"].handle(ReactionEvent("e", "C", plan_ts, "U9", "white_check_mark")).action
        == "ignore"
    )
    pump(ag, shared)
    assert [len(a.rt.inputs) for a in ag.values()] == [1, 1, 0]
    ask = next(
        m
        for m in shared.messages
        if m.metadata
        and m.metadata["event_payload"].get("access") == "approve"
        and m.metadata["event_payload"]["status"] == "needs_approval"
    )
    assert ask.sender_id == "B2" and "result of B2" in ask.text
    # context: step 1 got the text of step 0
    ctx = ag["B2"].rt.inputs[0].task["payload"]["context"]
    assert [c["text"] for c in ctx] == ["result of B1"]
    # a stranger cannot approve, the starter can
    assert ag["B2"].handle(ClickEvent("e", "C", ask.ts, "U77", "pipe_approve")).action == "ignore"
    assert ag["B2"].handle(ClickEvent("e", "C", ask.ts, "U9", "pipe_approve")).action == "approve"
    assert statuses(shared)[-1] == "done"
    hops = [m.metadata["event_payload"]["hop"] for m in shared.messages if m.metadata]
    assert max(hops) == 2


def test_hop_4_is_refused_once_and_runs_nothing():
    plan = {"steps": [step("B1"), step("B2", "cap-2")], "source": "free"}
    shared, ag = world(plan)
    shared.messages += [start_msg(2), claim(3, "B1", 0, "done"), handoff(4, "B1", "B2", 1, 0, 4)]
    pump(ag, shared)
    pump(ag, shared)
    refusals = [m for m in shared.messages if m.text.startswith("Stopped.")]
    assert len(refusals) == 1 and refusals[0].sender_id == "B2"
    assert all(not a.rt.inputs for a in ag.values())


def test_forged_handoff_from_unknown_bot_does_nothing():
    plan = {"steps": [step("B1"), step("B2", "cap-2")], "source": "free"}
    shared, ag = world(plan)
    shared.messages += [handoff(4, "B9", "B2", 1, 0, 1)]
    n = len(shared.messages)
    pump(ag, shared)
    assert len(shared.messages) == n and all(not a.rt.inputs for a in ag.values())


def test_tag_race_runs_the_step_once_on_the_lowest_claim():
    plan = {"steps": [step("B3", "cap-3"), step("any", "tag:review")], "source": "free"}
    shared, ag = world(plan)
    shared.messages += [
        start_msg(2, agent="B3"),
        claim(3, "B3", 0, "done"),
        handoff(4, "B3", "any", 1, 0, 2),
    ]
    # B2 claims at the same time as B1, but later
    ag["B1"].st.sleep = lambda s: shared.messages.append(claim(500, "B2", 1))
    pump({"B1": ag["B1"], "B2": ag["B2"]}, shared)
    assert len(ag["B1"].rt.inputs) == 1 and ag["B2"].rt.inputs == []
    assert any(
        m.sender_id == "B2" for m in shared.messages if m.metadata
    )  # its own claim stays kit
