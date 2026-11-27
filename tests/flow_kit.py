"""Rig for spec 006 flow tests: three adapters on one fake thread store, real templates."""

from pathlib import Path

from fakes import FakeRuntime, FakeTransport
from pipe import adapter
from pipe.config import Config
from pipe.core.capability import Capability
from pipe.core.contract import ClickEvent, MentionEvent, Message, ReactionEvent, RuntimeOutput
from pipe.core.scrub import scrub
from pipe.flows_io import load_flows, load_tags

FLOWS = Path(__file__).resolve().parents[1] / "flows"
TAGS = load_tags(FLOWS / "tags.yaml")
CH = "C"
CHANNELS = {"pipe-status": "CS", "pipe-work": CH, "pipe-agents": "CA"}
AGENTS = {
    "B1": ("UA", "OA", "agent-a"),
    "B2": ("UB", "OB", "agent-b"),
    "B3": ("UC", "OC", "agent-c"),
}
TRIG = {
    "bot_id": "BT", "bot_user_id": "UT", "owner": "OT", "name": "pipe-gitlab",
    "kind": "trigger", "skills": [], "description": "d", "mode": "ci", "hash": "h",
}  # fmt: skip
CHECK = "white_check_mark"


def meta(m):
    md = m.metadata or {}
    return md.get("event_payload", {}) if md.get("event_type") == "pipe.task.v1" else {}


class Transport(FakeTransport):
    def delete_message(self, channel, ts):  # in place: the store is shared
        self.deleted.append((channel, ts))
        self.messages[:] = [m for m in self.messages if (m.channel, m.ts) != (channel, ts)]


class Script(FakeRuntime):
    """Planner output in `plan_out`. Step outputs from `script` (an Exception is raised)."""

    def __init__(self):
        super().__init__()
        self.plan_out, self.script = None, []

    def run(self, inp):
        self.inputs.append(inp)
        if inp.task["purpose"] == "plan":
            assert self.plan_out is not None, "planner called"
            return RuntimeOutput("plan", data=self.plan_out)
        out = self.script.pop(0) if self.script else self.output
        if isinstance(out, Exception):
            raise out
        return out

    def steps(self):
        return [i for i in self.inputs if i.task["purpose"] == "step"]


def done(text="ok", **kw):
    return RuntimeOutput(text, "done", **kw)


class FlowRig:
    def __init__(self, offers=None, allowlist=(), flows=None, trigger=False):
        """`offers`: {bot_id: [tags]} (default: every agent offers every tag)."""
        self.offers = offers or {k: list(TAGS) for k in AGENTS}
        self.t = {k: Transport(k, v[0], CHANNELS) for k, v in AGENTS.items()}
        ta = self.t["B1"]
        for t in self.t.values():
            t.messages, t._ts = ta.messages, ta._ts  # one thread store
        ta._n = 100
        self.rt = {k: Script() for k in AGENTS}
        self.flows = load_flows(FLOWS, FLOWS / "none", TAGS) if flows is None else flows
        self.a = {k: self._make(k, allowlist) for k in AGENTS}
        for k, (user, owner, name) in AGENTS.items():  # newer than the published cards
            skills = [{"id": f"{x}-{k}", "tags": [x], "access": TAGS[x]} for x in self.offers[k]]
            card = {"bot_id": k, "bot_user_id": user, "owner": owner, "name": name,
                    "skills": skills, "description": "d", "kind": "agent", "mode": "laptop",
                    "hash": "h"}  # fmt: skip
            self._card(k, card)
        if trigger:
            self._card("BT", TRIG)
        self.n = 0

    def _card(self, bot, card):
        md = {"event_type": "pipe.card.v1", "event_payload": card}
        ts = self.t["B1"]._ts()
        self.t["B1"].messages.append(
            Message("CA", ts, ts, bot, True, "card", card["bot_user_id"], md)
        )

    def _make(self, k, allowlist):
        user, owner, name = AGENTS[k]
        caps = {
            f"{x}-{k}": Capability(f"{x}-{k}", x, tags=(x,), access=TAGS[x]) for x in self.offers[k]
        }
        a = adapter.build(
            Config(name, "keychain:x", owner=owner), self.t[k], self.rt[k], scrub,
            self.t[k].escape_mentions, flows=self.flows, caps=caps,
            stepper_kw={"sleep": lambda s: None, "allowlist": allowlist},
        )  # fmt: skip
        a.start()
        return a

    # --- events
    def raise_all(self, ev):
        for t in self.t.values():
            t.raise_event(ev)

    def _eid(self):
        self.n += 1
        return f"E{self.n}"

    def say(self, text, sender="U9"):
        """A human top-level message. Gives the parent message."""
        m = self.t["B1"].add_message(CH, text, sender_id=sender)
        self.raise_all(MentionEvent(CH, m.ts, m.thread, sender, False, text, self._eid()))
        return m

    def trigger(self, text, bot="BT", pipeline=None):
        pay = {"v": 1, "phase": "plan", "status": "needs_approval", "by": bot, "hop": 0}
        if pipeline:
            pay["pipeline"] = pipeline
        ts = self.t["B1"]._ts()
        md = {"event_type": "pipe.task.v1", "event_payload": pay}
        m = Message(CH, ts, ts, bot, True, text, "UT", md)
        self.t["B1"].messages.append(m)
        self.raise_all(MentionEvent(CH, ts, ts, bot, True, text, self._eid()))
        return m

    def react(self, m, who="U9"):
        self.raise_all(ReactionEvent(self._eid(), CH, m.ts, who, CHECK))

    def click(self, m, who, action):
        self.raise_all(ClickEvent(self._eid(), CH, m.ts, who, action))

    def reply(self, parent, text, sender="U9"):
        m = self.t["B1"].add_message(CH, text, sender_id=sender, thread=parent.ts)
        self.raise_all(MentionEvent(CH, m.ts, parent.ts, sender, False, text, self._eid()))
        return m

    def pump(self, limit=30):
        """Deliver every handoff (a message with `next`) to all adapters until quiet."""
        seen = 0
        for _ in range(limit):
            msgs = list(self.t["B1"].messages)
            new = [m for m in msgs[seen:] if meta(m).get("next")]
            seen = len(msgs)
            for m in new:
                self.raise_all(
                    MentionEvent(CH, m.ts, m.thread, m.sender_id, True, m.text, self._eid())
                )
            if len(self.t["B1"].messages) == seen:
                return

    # --- views
    def task(self, by=None, phase=None):
        out = [
            m
            for m in self.t["B1"].messages
            if (m.metadata or {}).get("event_type") == "pipe.task.v1"
        ]
        return [
            m for m in out
            if (by is None or meta(m)["by"] == by) and (phase is None or meta(m)["phase"] == phase)
        ]  # fmt: skip

    def plan(self):
        return next(m for m in self.task("B1", "plan") if meta(m).get("pipeline"))

    def plan_steps(self):
        return meta(self.plan())["pipeline"]["steps"]

    def posts(self):
        return [p for t in self.t.values() for p in t.posts]

    def buttons(self):
        """Posts and updates that carry buttons."""
        return [x for t in self.t.values() for x in t.posts + t.updates if x["buttons"]]

    def texts(self, top):
        """Texts of the plain (not task) posts in a thread."""
        return [p["text"] for p in self.posts() if p["thread"] == top.ts and not p["metadata"]]

    def final(self):
        """Latest status of a step or plan message that is not a claim."""
        return [meta(m)["status"] for m in self.task()][-1]

    def calls(self):
        return sum(len(r.steps()) for r in self.rt.values())

    def run_to_end(self, text, **kw):
        """Plan, ✅, pump. Gives (parent, plan message)."""
        top = self.say(text)
        plan = self.plan()
        self.react(plan)
        self.pump()
        return top, plan
