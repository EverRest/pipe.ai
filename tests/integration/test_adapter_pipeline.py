"""Stage 003 adapter: two agents on one shared fake thread store."""

from fakes import FakeRuntime, FakeTransport
from pipe import adapter
from pipe.config import Config
from pipe.core.capability import Capability
from pipe.core.contract import MentionEvent, Message, ReactionEvent, RuntimeOutput
from pipe.core.scrub import scrub
from thread_kit import CARDS, PARENT, TOP, claim, handoff, plan_msg, start_msg

CH = "C"
CHANNELS = {"pipe-status": "CS", "pipe-work": CH, "pipe-agents": "CA"}
CHECK = "white_check_mark"
STEPS = [
    {"agent": "B1", "access": "read", "goal": "look", "capability": "cap-1"},
    {"agent": "B2", "access": "read", "goal": "check", "capability": "cap-2"},
]


class PlanRuntime(FakeRuntime):
    def run(self, inp):
        self.inputs.append(inp)
        if inp.task["purpose"] == "plan":
            return RuntimeOutput("plan", data={"steps": STEPS})
        return RuntimeOutput("result")


def meta(m):
    return (m.metadata or {}).get("event_payload", {})


class Rig:
    def __init__(self):
        self.ta = FakeTransport("B1", "UA", CHANNELS)
        self.tb = FakeTransport("B2", "UB", CHANNELS)
        self.tb.messages, self.tb._ts = self.ta.messages, self.ta._ts  # one thread store
        self.ta._n = 100  # after the thread_kit timestamps
        self.top = TOP
        self.rt = PlanRuntime()
        self.a = self._make(self.ta, "agent-a", "OA", "cap-1")
        self.b = self._make(self.tb, "agent-b", "OB", "cap-2")
        for c in CARDS.values():  # newer than the cards the adapters published
            card = {**c, "description": "d", "kind": "agent", "mode": "laptop", "hash": "h"}
            md = {"event_type": "pipe.card.v1", "event_payload": card}
            ts = self.ta._ts()
            m = Message("CA", ts, ts, c["bot_id"], True, "card", c["bot_user_id"], md)
            self.ta.messages.append(m)

    def _make(self, t, name, owner, cap):
        caps = {cap: Capability(cap, cap)}
        a = adapter.build(
            Config(name, "keychain:x", owner=owner), t, self.rt, scrub, t.escape_mentions,
            caps=caps, stepper_kw={"sleep": lambda s: None},
        )  # fmt: skip
        a.start()
        return a

    def thread(self):
        return [m for m in self.ta.messages if m.thread == self.top]

    def task_msgs(self):
        return [m for m in self.thread() if meta(m)]


def mention(m, sender, eid, bot=True):
    return MentionEvent(CH, m.ts, m.thread, sender, bot, m.text, eid)


def test_two_agents_plan_approve_run_in_order_and_done():
    r = Rig()
    parent = r.ta.add_message(CH, PARENT, sender_id="U9")
    r.top = parent.ts
    r.ta.raise_event(mention(parent, "U9", "E1", bot=False))
    plan = r.ta.posts[-1]
    p = plan["metadata"]["event_payload"]
    assert (p["phase"], p["status"], p["by"], p["hop"]) == ("plan", "needs_approval", "B1", 0)
    assert p["pipeline"]["steps"] == STEPS and "agent-b" in plan["text"]
    r.ta.raise_event(ReactionEvent("R1", CH, plan["ts"], "U9", CHECK))
    start = r.ta.posts[-1]
    assert meta_of(start)["status"] == "done" and meta_of(start)["phase"] == "plan"
    r.ta.raise_event(mention(find(r, start["ts"]), "B1", "E2"))  # app_mention of the handoff
    hand = r.ta.posts[-1]
    assert meta_of(hand)["next"]["agent"] == "B2" and meta_of(hand)["hop"] == 2
    r.tb.raise_event(mention(find(r, hand["ts"]), "B1", "E3"))
    last = r.task_msgs()[-1]
    assert (meta(last)["by"], meta(last)["step"], meta(last)["status"]) == ("B2", 1, "done")
    assert "next" not in meta(last)
    steps = [i.task.get("step") for i in r.rt.inputs if i.task["purpose"] == "step"]
    assert steps == [0, 1]
    ran = [(meta(m)["by"], meta(m)["step"]) for m in r.task_msgs() if meta(m)["status"] == "done"]
    assert ran[-3:] == [("B1", 0), ("B2", 1), ("B2", 1)]  # step 1 handoff, then step 2


def work(t):
    """Task posts in the work channel (not the cards)."""
    return [p for p in t.posts if p["channel"] == CH and p["metadata"]]


def meta_of(post):
    return post["metadata"]["event_payload"]


def find(r, ts):
    return next(m for m in r.ta.messages if m.ts == ts)


def seed(r, *msgs):
    r.ta.add_message(CH, PARENT, sender_id="U9", ts=TOP)
    r.ta.messages.extend(msgs)


def test_forged_plan_from_another_card_holder_is_not_started():
    r = Rig()
    forged = plan_msg(2, by="B2")  # B2 has a card, but A is the planner
    seed(r, forged)
    ev = ReactionEvent("R9", CH, forged.ts, "U9", CHECK)
    r.ta.raise_event(ev)
    r.tb.raise_event(ev)
    assert not work(r.ta) + work(r.tb)
    assert r.rt.inputs == []


def test_bot_without_card_does_nothing():
    r = Rig()
    seed(r, plan_msg(), start_msg())
    h = handoff(5, "B1", "B1", 0, 0, 1)
    h = Message(CH, h.ts, TOP, "B9", True, "x", "U_X", h.metadata)  # no card for B9
    r.ta.messages.append(h)
    r.ta.raise_event(mention(h, "B9", "E5"))
    assert work(r.ta) == [] and r.rt.inputs == []


def test_hop_4_is_refused_and_runs_nothing():
    r = Rig()
    h = handoff(4, "B1", "B2", 1, 0, 4)
    seed(r, plan_msg(), start_msg(), claim(3, "B1", 0, "done"), h)
    r.tb.raise_event(mention(h, "B1", "E4"))
    out = work(r.tb)
    assert len(out) == 1 and meta_of(out[0])["status"] == "failed"
    assert meta_of(out[0])["reason"] == "hop limit exceeded"
    assert r.rt.inputs == []
