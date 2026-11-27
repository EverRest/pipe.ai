"""Routing: one event plus the thread state gives one decision. Pure.
Thread text is untrusted: every task message passes the card checks first."""

import re
from dataclasses import dataclass, field, fields
from types import SimpleNamespace
from typing import Any

from pipe.core.claim import claim_excluded, resolve_claim, ts_key
from pipe.core.contract import ClickEvent, MentionEvent, ReactionEvent
from pipe.core.gate import step_rejected
from pipe.core.pipeline import Pipeline, Step, matches_tag
from pipe.core.router import should_handle
from pipe.core.source import effective_source, hop_limit, parse_source
from pipe.core.trust import hop_refused, trusted_sender

TASK_EVENT = "pipe.task.v1"
CHECK = "white_check_mark"
UNVERIFIED = " (plan source not verified)"
_STATUS = ("needs_approval", "claimed", "running", "waiting", "done", "failed")
_NAME = re.compile(r"[a-z0-9-]{1,32}")
_TAG = re.compile(r"tag:([a-z0-9-]{1,32})")
_MENTION = re.compile(r"<@([A-Z0-9]+)>")
_STEP_FIELDS = {f.name for f in fields(Step)}
_NOT_CLAIM = ("owner offline", "no_claimer")  # posted by the handoff sender


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str = ""
    arg: Any = None


@dataclass(frozen=True)
class BotMessage:
    channel: str
    ts: str
    thread_ts: str
    sender_id: str
    payload: Any
    sender_handle: str | None = None
    event_id: str | None = None
    sender_is_bot: bool = True


@dataclass(frozen=True)
class Wake:
    thread_ts: str
    now: float


@dataclass(frozen=True)
class ThreadState:
    channel: str
    thread_ts: str
    starter: str | None
    parent_text: str
    messages: tuple  # transport Messages, any sender
    cards: dict  # agent_id -> trusted card dict
    agent_users: dict  # handle -> agent_id
    self_id: str
    self_handle: str
    in_flight: frozenset = frozenset()
    seen_event_ids: frozenset = frozenset()
    flows: Any = field(default_factory=dict)
    dialog_timeout_h: int = 24


def _ign(reason="") -> Decision:
    return Decision("ignore", reason)


def mentions(text: str) -> list[str]:
    return list(dict.fromkeys(_MENTION.findall(text or "")))


def first_agent(text: str, agent_users: dict) -> str | None:
    """Agent id of the first mention that has a card."""
    return next((agent_users[h] for h in mentions(text) if h in agent_users), None)


def flow_word(text: str) -> str | None:
    for w in (text or "").split():
        if w.startswith("flow:"):
            return w[5:] if _NAME.fullmatch(w[5:]) else None
    return None


def dialog_expired(question_ts: str, now: float, hours: float) -> bool:
    return now - float(question_ts) > hours * 3600


def card_view(cards: dict) -> dict:
    """Card dicts as objects, for `validate_plan` and `matches_tag`."""
    return {k: SimpleNamespace(**v) for k, v in cards.items()}


def owner_gate(p) -> bool:
    """Type 4 gate: a `write` claim that waits for the owner. A type 5 gate has `artifacts`."""
    return bool(
        p["phase"] == "step"
        and p["status"] == "needs_approval"
        and p.get("access") == "write"
        and "artifacts" not in p
        and not p.get("next")
    )


def _int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _valid(p) -> bool:
    return bool(
        isinstance(p, dict)
        and p.get("v") == 1
        and p.get("phase") in ("plan", "step")
        and p.get("status") in _STATUS
        and isinstance(p.get("by"), str)
        and _int(p.get("hop"))
        and p["hop"] >= 0
        and (p.get("step") is None or _int(p["step"]))
        and (p.get("next") is None or isinstance(p["next"], dict))
    )


def _payload(m, cards):
    meta = m.metadata or {}
    p = meta.get("event_payload")
    ok = meta.get("event_type") == TASK_EVENT and _valid(p)
    return p if ok and p["by"] == m.sender_id and trusted_sender(m, cards) else None


def _pipeline(raw) -> Pipeline:
    try:
        steps = tuple(
            Step(**{k: v for k, v in s.items() if k in _STEP_FIELDS}) for s in raw["steps"]
        )
        return Pipeline(steps, raw.get("source"))
    except Exception:
        return Pipeline((), None)


class View:
    """Trusted view of a thread: plan, step agents, step messages."""

    def __init__(self, ts: ThreadState):
        self.ts = ts
        self.planner = first_agent(ts.parent_text, ts.agent_users)
        pairs = ((m, _payload(m, ts.cards)) for m in ts.messages)
        self.base = sorted(((m, p) for m, p in pairs if p), key=lambda x: ts_key(x[0].ts))
        plans = [(m, p) for m, p in self.base if p["phase"] == "plan"]
        withp = [x for x in plans if isinstance(x[1].get("pipeline"), dict)]
        self.plan_any = bool(withp)
        mine = [x for x in withp if x[1]["by"] == self.planner]
        self.plan = mine[0] if mine else None
        raw = self.plan[1]["pipeline"] if self.plan else {}
        st = raw.get("steps")
        ok = isinstance(st, list) and all(isinstance(x, dict) for x in st)
        self.steps = st if ok else []
        self.pipe = _pipeline(raw)
        self.agent: dict[int, str | None] = {}
        self.msgs: dict[int, list] = {i: [] for i in range(len(self.steps))}
        self.claims: dict[int, list] = {}
        sm = [
            x
            for x in self.base
            if x[1]["phase"] == "step"
            and _int(x[1].get("step"))
            and 0 <= x[1]["step"] < len(self.steps)
        ]
        for i, s in enumerate(self.steps):
            cl = [
                x
                for x in sm
                if x[1]["step"] == i
                and not x[1].get("next")
                and x[1].get("access") != "approve"
                and x[1].get("reason") not in _NOT_CLAIM
                and self._eligible(i, x[1]["by"])
            ]
            self.claims[i] = cl
            objs = [SimpleNamespace(ts=m.ts, by=p["by"], status=p["status"]) for m, p in cl]
            win = resolve_claim(objs) or min(objs, key=lambda c: ts_key(c.ts), default=None)
            a = s.get("agent")
            self.agent[i] = (
                (win.by if win else None) if a == "any" else (None if a.startswith("human:") else a)
            )
        for i, s in enumerate(self.steps):
            human = str(s.get("agent")).startswith("human:")
            for m, p in sm:
                if p["step"] != i:
                    continue
                if human:
                    good = p["by"] == self.agent.get(i - 1)
                elif p.get("reason") in _NOT_CLAIM:
                    good = True
                else:
                    good = p["by"] == self.agent[i]
                if good:
                    self.msgs[i].append((m, p))

    def _eligible(self, i, by) -> bool:
        s = self.steps[i]
        a = s.get("agent")
        if a != "any":
            return a == by
        t = _TAG.fullmatch(s.get("capability") or "")
        card = self.ts.cards.get(by)
        return bool(t and card and matches_tag(SimpleNamespace(**card), t[1], s.get("access")))

    def last(self, i):
        return self.msgs[i][-1] if self.msgs.get(i) else None

    def status(self, i) -> str:
        x = self.last(i)
        return x[1]["status"] if x else "pending"

    def branched(self, i) -> bool:
        return any(
            p.get("next") and p.get("reason") == "run_failed" and p["status"] == "failed"
            for _, p in self.msgs.get(i, ())
        )

    def question(self):
        """Latest step message that waits for a dialog answer, as (message, payload)."""
        qs = [x for i in self.msgs for x in [self.last(i)] if x]
        qs = [x for x in qs if x[1]["status"] == "waiting" and x[1].get("reason") == "needs_input"]
        return max(qs, key=lambda x: ts_key(x[0].ts), default=None)

    def gate_pending(self, i) -> bool:
        x = self.last(i)
        ok = x and x[1]["status"] == "needs_approval" and x[1].get("access") != "approve"
        return bool(ok and not owner_gate(x[1]))

    def owner_gate_pending(self, i) -> bool:
        x = self.last(i)
        return bool(x and owner_gate(x[1]))

    def rejected(self, i) -> bool:
        """FR-046: the latest claim of step `i` is `failed`, `rejected`."""
        cl = [
            SimpleNamespace(step=i, ts=m.ts, status=p["status"], reason=p.get("reason"))
            for m, p in self.claims.get(i, ())
        ]
        return step_rejected(cl, i)

    def started(self) -> bool:
        return any(
            p["phase"] == "plan" and p["status"] == "done" and p["by"] == self.planner
            for _, p in self.base
        )

    def owner(self, agent) -> str | None:
        return (self.ts.cards.get(agent) or {}).get("owner") or None

    def allowed(self, sender, agent) -> bool:
        """Thread starter or the card owner of `agent`."""
        return bool(sender) and sender in (self.ts.starter, self.owner(agent))


def find_plan(ts: ThreadState):
    return View(ts).plan


def open_question(ts: ThreadState):
    return View(ts).question()


def gate_pending(ts: ThreadState, i: int) -> bool:
    return View(ts).gate_pending(i)


def step_status(ts: ThreadState, i: int) -> str:
    return View(ts).status(i)


def step_agent(ts: ThreadState, i: int) -> str | None:
    return View(ts).agent.get(i)


def hop_refusal(v: View) -> str:
    """Refusal reason; the suffix says a declared template did not verify."""
    p = v.pipe
    src = effective_source(p, v.ts.flows, v.ts.cards, v.ts.starter)
    bad = src == "free" and parse_source(p.source) is not None
    return "hop limit exceeded" + (UNVERIFIED if bad else "")


def _limit(v: View) -> int:
    p = v.pipe
    return hop_limit(effective_source(p, v.ts.flows, v.ts.cards, v.ts.starter))


def _human(ev: MentionEvent, v: View) -> Decision:
    ts = v.ts
    if ev.sender_is_bot or ev.sender_id in (ts.self_id, ts.self_handle):
        return _ign("bot sender")
    if ev.event_id and (ev.event_id in ts.seen_event_ids or ev.event_id in ts.in_flight):
        return _ign("event handled")
    agents = list(
        dict.fromkeys(ts.agent_users[h] for h in mentions(ev.text) if h in ts.agent_users)
    )
    top, flow = ev.thread_ts == ev.ts, flow_word(ev.text)
    if top and (len(agents) >= 2 or (agents and flow)):
        if agents[0] != ts.self_id:
            return _ign("not_planner")
        planned = any(p["phase"] == "plan" and p["by"] == ts.self_id for _, p in v.base)
        if planned or f"plan:{ev.channel}:{ev.ts}" in ts.in_flight:
            return _ign("already_planned")
        return Decision("plan_flow", arg=flow) if flow else Decision("plan")
    q = None if top else v.question()
    if q:
        me = ts.self_handle in mentions(ev.text)
        if q[1]["by"] == ts.self_id and me and v.allowed(ev.sender_id, ts.self_id):
            return Decision("resume", arg=(q[0], ev))
        handle = (ts.cards.get(q[1]["by"]) or {}).get("bot_user_id")
        if q[1]["by"] != ts.self_id and not me and handle in mentions(ev.text):
            return _ign("not_for_me")
    d = should_handle(ev, ts.self_handle, "<@{}>".format, ts.seen_event_ids, (), ts.in_flight)
    return Decision({"reply": "chat"}.get(d.action, d.action), d.reason)


def _bot(ev: BotMessage, v: View) -> Decision:
    ts, p = v.ts, ev.payload
    if not trusted_sender(ev, ts.cards):
        return _ign("no_card")
    if not _valid(p):
        return _ign("bad_payload")
    if p["by"] != ev.sender_id:
        return _ign("by_mismatch")
    nxt = p.get("next")
    if not isinstance(nxt, dict):
        return _ign("no_next")
    if p["status"] not in ("done", "failed") or (p["status"] == "failed") != (
        p.get("reason") == "run_failed"
    ):
        return _ign("not_handoff")
    if not v.plan:
        return _ign("not_planner" if v.plan_any else "no_plan")
    if p["phase"] != "plan" and not v.started():
        return _ign("not_started")
    i = (nxt.get("payload") or {}).get("step")
    if not _int(i) or not 0 <= i < len(v.steps):
        return _ign("bad_payload")
    step, me = v.steps[i], ts.self_id
    if p["phase"] == "plan":
        if p["by"] != v.planner or i != 0:
            return _ign("not_planner")
    else:
        src = p.get("step")
        if not _int(src) or not 0 <= src < len(v.steps) or v.agent.get(src) != p["by"]:
            return _ign("not_assigned")
        branch = p["status"] == "failed"
        if i != (v.steps[src].get("on_fail") if branch else src + 1):
            return _ign("bad_branch" if branch else "bad_next")
        if branch and any(
            x[1].get("next") and x[1]["status"] == "failed" and x[0].ts != ev.ts
            for x in v.msgs[src]
        ):
            return _ign("already_branched")
    a = nxt.get("agent")
    if a == "any":
        if step.get("agent") != "any" or not v._eligible(i, me):
            return _ign("not_assigned" if step.get("agent") != "any" else "not_eligible")
    elif a != me:
        return _ign("not_for_me")
    elif step.get("agent") != me:
        return _ign("not_assigned")
    # access comes from the plan; the message must agree with it
    if step.get("access") not in ("read", "write") or nxt.get("access") != step["access"]:
        return _ign("unsupported_access")
    refused = any(
        x[1]["status"] == "failed" and str(x[1].get("reason", "")).startswith("hop limit exceeded")
        for x in v.base
    )
    if hop_refused(p["hop"], _limit(v)):
        return _ign("already_refused") if refused else Decision("refuse", hop_refusal(v), ev)
    if refused:
        return _ign("stopped")
    if claim_excluded(v.pipe.steps[i], me, v.agent.get):
        return _ign("excluded")
    if v.rejected(i):
        return _ign("rejected")
    own = any(ts_key(m.ts) > ts_key(ev.ts) and p2["by"] == me for m, p2 in v.msgs[i])
    if own or f"step:{ts.channel}:{ts.thread_ts}:{i}" in ts.in_flight:
        return _ign("already_claimed")
    return Decision("claim", arg=(ev, i))


def _reaction(ev: ReactionEvent, v: View) -> Decision:
    ts = v.ts
    if ev.name != CHECK:
        return _ign("other_reaction")
    hit = next((x for x in v.base if x[0].ts == ev.item_ts), None)
    if not hit or hit[1]["by"] != ts.self_id:
        return _ign("no_target")
    m, p = hit
    # Plan and gate are released by the starter or the planner owner (Q3).
    ok = bool(ev.sender_id) and ev.sender_id in (ts.starter, v.owner(v.planner))
    if p["phase"] == "plan":
        if p["status"] != "needs_approval" or not v.plan or v.plan[0].ts != m.ts:
            return _ign("not_plan")
        if not ok:
            return _ign("not_allowed")
        return _ign("already_started") if v.started() else Decision("start", arg=m)
    i = p.get("step")
    if p["status"] != "needs_approval" or p.get("access") == "approve" or p.get("next"):
        return _ign("not_gate")
    if not _int(i) or not v.gate_pending(i) or v.last(i)[0].ts != m.ts:
        return _ign("not_pending")
    return Decision("release", arg=m) if ok else _ign("not_allowed")


def _click(ev: ClickEvent, v: View) -> Decision:
    ts = v.ts
    hit = next((x for x in v.base if x[0].ts == ev.message_ts), None)
    if not hit or hit[1]["by"] != ts.self_id:
        return _ign("no_target")
    m, p = hit
    i = p.get("step")
    if ev.action_id in ("pipe_accept", "pipe_reject"):
        owner = v.owner(ts.self_id)
        if not owner or ev.sender_id != owner:
            return _ign("not_owner")
        if not (_int(i) and v.owner_gate_pending(i) and v.last(i)[0].ts == m.ts):
            return _ign("not_pending")
        return Decision(ev.action_id[5:], arg=m)
    if not v.allowed(ev.sender_id, ts.self_id):
        return _ign("not_allowed")
    if ev.action_id == "pipe_approve":
        cur = v.last(i) if _int(i) and i < len(v.steps) else None
        if cur and cur[0].ts == m.ts and p.get("access") == "approve":
            return Decision("approve", arg=m) if p["status"] == "needs_approval" else _ign("done")
        return _ign("not_approvable")
    if ev.action_id == "pipe_retry" and p["phase"] == "step" and _int(i) and i < len(v.steps):
        if p["status"] != "failed" or p.get("reason") == "rejected":
            return _ign("not_failed")
        if v.branched(i):
            return _ign("already_branched")
        if v.last(i)[0].ts != m.ts:
            return _ign("not_latest")
        return Decision("retry", arg=(m, i))
    return _ign("unknown_action")


def wake(ev: Wake, v: View) -> list[Decision]:
    ts, out = v.ts, []
    me = ts.self_id
    for i in range(len(v.steps)):
        x = v.last(i)
        busy = x and x[1]["by"] == me and x[1]["status"] in ("claimed", "running")
        if busy and f"step:{ts.channel}:{ts.thread_ts}:{i}" not in ts.in_flight:
            out.append(Decision("interrupt", arg=x[0]))
    q = v.question()
    if q and q[1]["by"] == me and dialog_expired(q[0].ts, ev.now, ts.dialog_timeout_h):
        out.append(Decision("expire_dialog", arg=q[0]))
    last_h: dict[int, tuple] = {}
    for m, p in v.base:  # latest handoff for each target step
        i = ((p.get("next") or {}).get("payload") or {}).get("step")
        if _int(i) and p["status"] in ("done", "failed"):
            last_h[i] = (m, p)
    for i, (m, p) in last_h.items():
        later = [x for x in v.msgs.get(i, ()) if ts_key(x[0].ts) > ts_key(m.ts)]
        if any(p2.get("reason") != "owner offline" for _, p2 in later):
            continue
        d = _bot(BotMessage(m.channel, m.ts, ts.thread_ts, m.sender_id, p, m.sender_handle), v)
        if d.action == "claim":
            out.append(d)
    for m, p in v.base:
        reacted = {u for r in m.reactions if r.get("name") == CHECK for u in r.get("users", ())}
        gate = p["phase"] == "step" and _int(p.get("step")) and p["step"] < len(v.steps)
        gate = gate and p["status"] == "needs_approval" and v.gate_pending(p["step"])
        plan = p["phase"] == "plan" and p["status"] == "needs_approval" and not v.started()
        if p["by"] == me and (plan or gate) and reacted & {ts.starter, v.owner(v.planner)} - {None}:
            out.append(Decision("start" if plan else "release", arg=m))
    mine = any(p["phase"] == "plan" and p["by"] == me for _, p in v.base)
    agents = [ts.agent_users[h] for h in mentions(ts.parent_text) if h in ts.agent_users]
    flow = flow_word(ts.parent_text)
    if not mine and agents and agents[0] == me and (len(set(agents)) > 1 or flow):
        out.append(Decision("plan_flow", arg=flow) if flow else Decision("plan"))
    return out


def route(event, ts: ThreadState) -> Decision:
    """One decision. A `Wake` gives the first one; use `wake_all` for all."""
    v = View(ts)
    if isinstance(event, Wake):
        return (wake(event, v) or [_ign("nothing to do")])[0]
    if isinstance(event, BotMessage):
        return _bot(event, v)
    if isinstance(event, ReactionEvent):
        return _reaction(event, v)
    if isinstance(event, ClickEvent):
        return _click(event, v)
    if isinstance(event, MentionEvent):
        return _human(event, v)
    return _ign("unknown event")


def wake_all(event: Wake, ts: ThreadState) -> list[Decision]:
    return wake(event, View(ts))
