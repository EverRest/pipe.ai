"""Rig for spec 004 gate tests: two adapters (B1 owner OA, B2 owner OB) on one thread store."""

from fakes import FakeRuntime, FakeTransport
from pipe import adapter
from pipe.config import Config
from pipe.core.capability import Capability
from pipe.core.contract import ClickEvent, MentionEvent, Message
from pipe.core.scrub import scrub
from thread_kit import CARDS, PARENT, TOP, claim, plan_msg, start_msg, step, task

CH = "C"
CHANNELS = {"pipe-status": "CS", "pipe-work": CH, "pipe-agents": "CA"}
WRITE = {"steps": [step("B1"), {**step("B2", "cap-2"), "access": "write"}], "source": "free"}


def meta(m):
    return (m.metadata or {}).get("event_payload", {})


class Rig:
    def __init__(self, allowlist=(), names=None):
        self.ta = FakeTransport("B1", "UA", CHANNELS)
        self.tb = FakeTransport("B2", "UB", CHANNELS)
        self.tb.messages, self.tb._ts = self.ta.messages, self.ta._ts  # one thread store
        self.ta._n = 100
        self.rt_a, self.rt_b = FakeRuntime(), FakeRuntime()
        self.allowlist = list(allowlist)
        self.a = self._make(self.ta, self.rt_a, "agent-a", "OA", "cap-1", [])
        self.b = self._make(self.tb, self.rt_b, "agent-b", "OB", "cap-2", self.allowlist)
        for k, c in CARDS.items():  # newer than the cards the adapters published
            c = {**c, "name": (names or {}).get(k, c["name"])}
            card = {**c, "description": "d", "kind": "agent", "mode": "laptop", "hash": "h"}
            md = {"event_type": "pipe.card.v1", "event_payload": card}
            ts = self.ta._ts()
            m = Message("CA", ts, ts, c["bot_id"], True, "card", c["bot_user_id"], md)
            self.ta.messages.append(m)

    def _make(self, t, rt, name, owner, cap, allowlist):
        a = adapter.build(
            Config(name, "keychain:x", owner=owner), t, rt, scrub, t.escape_mentions,
            caps={cap: Capability(cap, cap)},
            stepper_kw={"sleep": lambda s: None, "allowlist": allowlist},
        )  # fmt: skip
        a.start()
        return a

    def restart_b(self):
        self.b = self._make(self.tb, self.rt_b, "agent-b", "OB", "cap-2", self.allowlist)

    def seed(self, starter="U9", plan=WRITE, access="write", sender="B1"):
        """Parent post, plan, start, step 0 done, handoff of step 1. Gives the handoff."""
        self.ta.add_message(CH, f"{PARENT}", sender_id=starter, ts=TOP)
        nxt = {"agent": "B2", "access": access, "payload": {"step": 1}}
        h = task(
            4, sender, "step", "done", 2, step=0, access="read", next=nxt, artifacts=[], text=""
        )
        self.ta.messages.extend([plan_msg(plan=plan), start_msg(), claim(3, "B1", 0, "done"), h])
        return h

    def handoff(self, h, eid="E1"):
        self.tb.raise_event(MentionEvent(CH, h.ts, h.thread, h.sender_id, True, h.text, eid))

    def click(self, m, who, action="pipe_accept", eid="K1"):
        self.tb.raise_event(ClickEvent(eid, CH, m.ts, who, action))

    def step_msgs(self, by="B2"):
        return [m for m in self.ta.messages if meta(m).get("by") == by and meta(m).get("step") == 1]

    def gate(self):
        """The latest claim of B2 for step 1."""
        return self.step_msgs()[-1]
