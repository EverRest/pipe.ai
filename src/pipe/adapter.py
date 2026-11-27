"""Composition root and main loop. Imports no Slack module (FR-020)."""

import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from pipe import state
from pipe.capset import collect
from pipe.card_sync import sync_card
from pipe.cards import CardCache
from pipe.config import Config
from pipe.core.card import Identity as CardIdentity
from pipe.core.card import build_card
from pipe.core.catchup import parents_to_scan, pick_missed
from pipe.core.contract import (
    ClickEvent,
    MentionEvent,
    Message,
    ReactionEvent,
    RuntimeFailed,
    RuntimeInput,
)
from pipe.core.dedupe import remember
from pipe.core.exposure import render_list, state_of
from pipe.core.flows import expand as expand_flow
from pipe.core.flows import missing_tags, parse_flow_mention
from pipe.core.pipeline import validate_plan
from pipe.core.render import render_plan, render_trigger
from pipe.core.route import (
    TASK_EVENT,
    BotMessage,
    ThreadState,
    Wake,
    card_view,
    route,
    wake_all,
)
from pipe.core.router import is_owner, should_handle
from pipe.core.status import parse_status_messages, recent, render_summary
from pipe.core.summary import build_summary
from pipe.core.trigger import decide_trigger
from pipe.flows_io import load_default
from pipe.owner_summary import send_summary
from pipe.planner import PlanResult, plan
from pipe.stepper import GATE, Stepper

WEEK = 7 * 86400
log = logging.getLogger("pipe.adapter")


def _setup_log() -> None:
    p = state.pipe_home() / "logs" / "adapter.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=p, level=logging.INFO, format="%(asctime)s %(message)s")


class Adapter:
    def __init__(
        self,
        cfg: Config,
        transport,
        runtime,
        scrub_fn: Callable,
        escape_fn: Callable,
        *,
        flows: dict | None = None,
        expand: Callable | None = None,
        caps: dict | None = None,
        stepper_kw: dict | None = None,
    ):
        """`flows`/`expand`: template store and expansion (spec 006; empty until wired).
        `caps`: exposed capabilities by id (default: found at start). `stepper_kw`: timer etc."""
        self.cfg, self.t, self.rt = cfg, transport, runtime
        self.flows, self.expand, self.caps = flows or {}, expand, dict(caps or {})
        kw = {"allowlist": getattr(cfg, "allowlist", ()), **(stepper_kw or {})}
        self.stepper = Stepper(transport, runtime, self._state, self.caps, **kw)
        self.cards: CardCache | None = None
        self.threads: dict[tuple, str] = {}  # (channel, ts) -> thread ts; ponytail: grows per run
        self.handle = ""
        self.scrub, self.esc = scrub_fn, escape_fn
        seen = state.load_seen()
        self.event_ids, self.keys = seen["event_ids"], seen["mention_keys"]
        self.in_flight: set[str] = set()
        self.submit: Callable = lambda f, *a: f(*a)  # run_forever swaps in one worker thread
        self.agent_id = ""

    def _safe(self, text: str) -> str:
        return self.esc(self.scrub(text))

    # Receipt: decide, then mark in flight (memory only).
    def _accept(self, e: MentionEvent, who: str = ""):
        d = should_handle(
            e, who or self.agent_id, self.t.mention, self.event_ids, self.keys, self.in_flight
        )
        if d.action == "ignore":
            return None
        self.in_flight.update({f"{e.channel}:{e.ts}", *([e.event_id] if e.event_id else [])})
        return d

    # --- stage 003: thread state, routing, decisions
    def _cards(self) -> dict:
        try:
            if self.cards is None:
                self.cards = CardCache(self.t, self.t.find_channel(self.cfg.agents_channel))
            return self.cards.cards()
        except Exception as x:
            log.info("no cards: %s", type(x).__name__)
            return {}

    def _state(self, channel: str, thread_ts: str) -> ThreadState:
        msgs = tuple(self.t.replies(channel, thread_ts))
        for m in msgs:
            self.threads[(channel, m.ts)] = m.thread
        parent = next((m for m in msgs if m.ts == thread_ts), None)
        cards = self._cards()
        users = self.cards.agent_users() if self.cards else {}
        return ThreadState(
            channel, thread_ts, parent.sender_id if parent else None,
            parent.text if parent else "", msgs, cards, users, self.agent_id, self.handle,
            frozenset(self.in_flight), frozenset(self.event_ids), self.flows,
            self.stepper.dialog_timeout_h,
        )  # fmt: skip

    def _thread_of(self, channel: str, ts: str) -> str | None:
        """Thread of a reacted or clicked message: from memory, else a scan of recent parents."""
        if (channel, ts) in self.threads:
            return self.threads[(channel, ts)]
        for p in self.t.history(channel, limit=100):
            if p.ts == ts or (
                p.latest_reply and any(m.ts == ts for m in self.t.replies(channel, p.ts))
            ):
                return p.thread
        return None

    def _bot_event(self, e: MentionEvent) -> BotMessage | None:
        """A mention from a bot is a handoff only when the message holds task metadata."""
        m = next((x for x in self.t.replies(e.channel, e.thread_ts) if x.ts == e.ts), None)
        md = (m.metadata or {}) if m else {}
        if md.get("event_type") != TASK_EVENT:
            return None
        self._cards()
        if self.cards:
            self.cards.note_sender(m.sender_id)
        return BotMessage(
            e.channel, e.ts, e.thread_ts, m.sender_id, md.get("event_payload"),
            m.sender_handle, e.event_id, m.sender_is_bot, m.text,
        )  # fmt: skip

    def _keys(self, e, d, channel: str) -> set[str]:
        keys = {k for k in (getattr(e, "event_id", None),) if k}
        if isinstance(e, MentionEvent):
            keys.add(f"{channel}:{e.ts}")
        if d.action in ("plan", "plan_flow"):
            keys.add(f"plan:{channel}:{e.ts if hasattr(e, 'ts') else e.thread_ts}")
        if d.action == "claim":
            keys.add(f"step:{channel}:{d.arg[0].thread_ts}:{d.arg[1]}")
        if d.action in ("accept", "reject", "reject_plan"):
            keys.add(f"{d.action}:{channel}:{d.arg.ts}")
        if d.action == "trigger":
            keys.add(f"trigger:{channel}:{d.arg.ts}")
        return keys

    def _decide(self, e):
        """Receipt: route one event. Gives a job (function and args) or None. Marks in flight."""
        if isinstance(e, MentionEvent):
            thread = e.thread_ts
            if e.sender_is_bot and not (e := self._bot_event(e)):
                return None
        elif isinstance(e, ReactionEvent | ClickEvent):
            if e.event_id and (e.event_id in self.event_ids or e.event_id in self.in_flight):
                return None
            thread = self._thread_of(e.channel, getattr(e, "item_ts", None) or e.message_ts)
        else:
            return None
        if not thread:
            return None
        d = route(e, self._state(e.channel, thread))
        if isinstance(e, MentionEvent) and (
            d.action in ("chat", "status_query") or d.reason == "no mention"
        ):
            # stage 001 path: its tag is the agent id, the routed one is the handle
            if old := self._accept(e, self.handle) or self._accept(e, self.agent_id):
                return self._process, e, old.action
            return None
        if d.reason == "not_owner":
            log.info("gate click ignored: not the owner")
        keys = self._keys(e, d, e.channel)
        if d.action == "ignore" or keys & self.in_flight:
            return None
        self.in_flight |= keys
        return self._run, e, d, keys, (e.channel, thread)

    def on_event(self, e) -> None:
        try:
            if job := self._decide(e):
                self.submit(*job)
        except Exception:
            log.exception("event failed")

    def _run(self, e, d, keys, where) -> None:
        """Run one decision. An error is logged: one thread never stops the adapter."""
        try:
            res = self._act(e, d, where)
            if eid := getattr(e, "event_id", None):
                self.event_ids = remember(self.event_ids, eid)
            if isinstance(e, MentionEvent | BotMessage):
                self.keys = remember(self.keys, f"{e.channel}:{e.ts}")
                if res != "needs_approval":  # a waiting gate keeps the handoff unseen
                    state.save_state(last_seen_ts=e.ts)
            state.save_seen(self.event_ids, self.keys)
        except Exception:
            log.exception("%s failed", d.action)
        finally:
            self.in_flight -= keys

    def _act(self, e, d, where) -> None:
        st, a = self.stepper, d.action
        if a in ("plan", "plan_flow"):
            self._plan(d, self._state(*where))
        elif a == "trigger":
            self._trigger(d.arg, self._state(*where))
        elif a == "start":
            ts = self._state(d.arg.channel, d.arg.thread)
            if isinstance(e, ClickEvent):  # Accept on a trigger plan
                st.accept_plan(ts, d.arg)
            else:
                st.start_pipeline(ts, d.arg)
        elif a == "reject_plan":
            st.reject_plan(d.arg)
        elif a == "claim":
            return st.run_step(*d.arg)
        elif a == "refuse":
            st.refuse(e, d.reason)
        elif a == "approve":
            st.approve_step(d.arg)
        elif a == "release":
            st.release_step(d.arg)
        elif a == "accept":
            st.accept_step(d.arg)
        elif a == "reject":
            st.reject_step(d.arg)
        elif a == "retry":
            st.retry_step(*d.arg)
        elif a == "resume":
            st.resume_step(d.arg[0])
        elif a == "expire_dialog":
            st.expire_dialog(d.arg.thread, d.arg.ts, d.arg.channel)
        elif a == "interrupt":
            st.interrupt(d.arg)

    def _plan(self, d, ts: ThreadState) -> None:
        cards = card_view(ts.cards)
        if d.action == "plan_flow":
            m = parse_flow_mention(ts.parent_text, ts.agent_users)
            res = self._flow_plan(d.arg, cards, ts.starter, m)
            if res.errors == ["unknown flow"]:
                known = ", ".join(sorted(self.flows)) or "none"
                res = PlanResult(errors=[f"flow {d.arg} not found. Known flows: {known}"])
        else:
            res = plan(
                ts.parent_text, cards, self.flows, self.rt, ts.starter,
                self._expander(ts.parent_text, cards, ts.starter),
            )  # fmt: skip
        if res.errors:
            text = self._safe("I could not build a plan: " + "; ".join(res.errors)[:300])
            self.t.post_message(ts.channel, text, thread=ts.thread_ts)
            return
        p = {
            "v": 1, "task_id": ts.thread_ts, "phase": "plan", "status": "needs_approval",
            "by": ts.self_id, "hop": 0, "step": 0,
            "pipeline": {"steps": res.steps, "source": res.source},
        }  # fmt: skip
        names = {k: c.get("name", k) for k, c in ts.cards.items()}
        text = self._safe(render_plan(res.steps, names))
        meta = {"event_type": TASK_EVENT, "event_payload": p}
        self.t.post_message(ts.channel, text, thread=ts.thread_ts, metadata=meta)

    def _trigger(self, t, ts: ThreadState) -> None:
        """Plan a trigger (no runtime call). Gate: allowlist starts it, else the owner decides."""
        cards, me = card_view(ts.cards), ts.cards.get(ts.self_id) or {}
        if t.flow:
            m = parse_flow_mention(f"flow:{t.flow} {t.title}", {})
            res = self._flow_plan(t.flow, cards, t.sender, m)
            errs = (
                ["could not build a plan (unknown flow)"]
                if res.errors == ["unknown flow"]
                else res.errors
            )
            steps, source = res.steps, res.source
        else:
            steps = [{k: v for k, v in vars(x).items() if v is not None} for x in t.pipeline.steps]
            source = "free"  # never read from the trigger; a template match is a spec 006 job
            errs = validate_plan({"steps": steps, "source": source}, cards, t.sender, self.flows)
        owner = me.get("owner")
        errs = errs or ([] if owner else ["no owner"])
        base = {
            "v": 1,
            "task_id": ts.thread_ts,
            "phase": "plan",
            "by": ts.self_id,
            "hop": 0,
            "step": 0,
        }
        post = lambda text, p, b=None: self.t.post_message(  # noqa: E731
            ts.channel, text, ts.thread_ts, {"event_type": TASK_EVENT, "event_payload": p}, b
        )
        if errs:
            reason = "; ".join(errs)
            post(
                self._safe("Plan rejected. " + reason[:300]),
                {**base, "status": "failed", "reason": reason[:200]},
            )
            return
        p = {**base, "status": "needs_approval", "pipeline": {"steps": steps, "source": source}}
        names = {k: c.get("name", k) for k, c in ts.cards.items()}
        if decide_trigger(t.sender, self.stepper.allowlist)[0] == "allow":
            post(self._safe(render_plan(steps, names, footer="Trigger allowed: starting.")), p)
            self.stepper.start_pipeline(self._state(ts.channel, ts.thread_ts), None)
            return
        who = (ts.cards.get(t.sender) or {}).get("name") or "trigger"
        ask = render_trigger(who, "needs approval", owner=self.t.mention(owner), escape=self.esc)
        post(self._safe(render_plan(steps, names, footer="")).rstrip() + "\n" + ask, p, GATE)

    def _expander(self, goal, cards, starter) -> Callable:
        """The planner gets `expand(name)`. The goal and the cards stay in the core call."""
        if self.expand:
            return self.expand

        def run(name):
            try:
                return expand_flow(self.flows[name], goal, None, starter, None, cards)
            except ValueError:
                return None

        return run

    def _flow_plan(self, name, cards, starter, m=None) -> PlanResult:
        flow = self.flows.get(name)
        if flow is None:
            return PlanResult(errors=["unknown flow"])
        if self.expand:  # injected expansion (tests, spec 005)
            t = self.expand(name)
            if not t:
                return PlanResult(errors=["unknown flow"])
        else:
            agents = m.agents if m else []
            takes = any(x["kind"] == "agent" for x in flow.steps)
            if takes and len(agents) < 2:
                return PlanResult(errors=[f"flow {name} needs a second agent mention"])
            if not takes and len(agents) > 1:
                return PlanResult(errors=[f"flow {name} takes no agent mention"])
            agent = agents[1] if takes else None
            params = m.params if m else {}
            try:  # bad parameters first, then the tags
                t = expand_flow(flow, m.goal if m else "", params, starter, agent, cards)
            except ValueError as e:
                return PlanResult(errors=[str(e)])
            if miss := missing_tags(flow, cards, params, agent):
                return PlanResult(errors=[f"flow {name}: missing tags: {', '.join(miss)}"])
        raw = {"steps": t["steps"], "source": t["source"]}
        errs = validate_plan(raw, cards, starter, self.flows)
        return PlanResult(errors=errs) if errs else PlanResult(list(t["steps"]), name, t["source"])

    def wake_pass(self) -> None:
        """Catch-up for pipelines: ask `wake_all` about each recent thread of the work channel."""
        try:
            ch = self.t.find_channel(self.cfg.work_channel)
            parents = self.t.history(ch, oldest=str(time.time() - WEEK))
        except Exception as x:
            log.info("no wake pass: %s", type(x).__name__)
            return
        for p in parents:
            try:
                w = Wake(p.ts, time.time())
                for d in wake_all(w, self._state(ch, p.ts)):
                    keys = self._keys(w, d, ch)
                    if keys & self.in_flight:
                        continue
                    self.in_flight |= keys
                    self._run(w, d, keys, (ch, p.ts))
            except Exception:
                log.exception("wake failed for %s", p.ts)

    def _process(self, e: MentionEvent, action: str) -> None:
        key = f"{e.channel}:{e.ts}"
        try:
            text = self._status() if action == "status_query" else self._reply(e)
            self.t.post_message(e.channel, text, thread=e.thread_ts)
            # Record only after the post (research.md D5).
            if e.event_id:
                self.event_ids = remember(self.event_ids, e.event_id)
            self.keys = remember(self.keys, key)
            state.save_seen(self.event_ids, self.keys)
            state.save_state(last_seen_ts=e.ts)
        except Exception:
            log.exception("mention %s failed", key)  # not seen: a restart retries
        finally:
            self.in_flight -= {key, e.event_id}

    def _reply(self, e: MentionEvent) -> str:
        msgs = self.t.replies(e.channel, e.thread_ts)
        thread = [{"user": m.sender_handle or m.sender_id, "text": m.text} for m in msgs]
        # Tools only if the trigger and the whole thread are owner or this agent's own bot.
        owner_only = is_owner(e.sender_id, self.cfg.owner) and all(
            m.sender_id == self.agent_id or is_owner(m.sender_id, self.cfg.owner) for m in msgs
        )
        inp = RuntimeInput(
            thread,
            {"id": uuid.uuid4().hex, "purpose": "chat"},
            owner_only,
        )
        try:
            out = self.rt.run(inp)
            if out.status != "failed":
                return self._safe(out.text)
            reason = out.reason or "failed"
        except RuntimeFailed as x:
            reason = str(x)
        except Exception:
            log.exception("runtime error")
            reason = "internal error"
        return self._safe(f"I could not finish this task. Reason: {reason[:200]}.")

    def _status(self) -> str:
        ch = self.t.find_channel(self.cfg.status_channel)
        msgs = self.t.history(ch, oldest=str(time.time() - WEEK))
        return render_summary(recent(parse_status_messages(msgs), int(time.time())), self.esc)

    def catch_up(self) -> None:
        last = state.load_state().get("last_seen_ts") or "0"
        chans = dict.fromkeys(
            [*self.t.member_channels(), self.t.find_channel(self.cfg.status_channel)]
        )
        missed: list[Message] = []
        for ch in chans:
            try:  # one broken channel must not starve the others
                hist = self.t.history(ch, oldest=str(max(float(last) - WEEK, 0)))
                msgs = {}
                for p in parents_to_scan(hist, last):
                    msgs.update({m.ts: m for m in [p, *self.t.replies(ch, p.ts, oldest=last)]})
                missed += pick_missed(
                    list(msgs.values()), self.agent_id, last, {*self.keys, *self.in_flight},
                    self.t.mention,
                )  # fmt: skip
            except Exception:
                log.exception("catch-up failed for %s", ch)
        for m in sorted(missed, key=lambda m: float(m.ts)):
            e = MentionEvent(m.channel, m.ts, m.thread, m.sender_id, m.sender_is_bot, m.text)
            if d := self._accept(e):
                self._process(e, d.action)
        self.wake_pass()

    def publish_capabilities(self, me) -> None:
        """Log the list, sync the card, DM the summary. An error is logged, never raised."""
        try:
            caps, notes = collect(self.cfg)
            for ln in render_list(caps, self.cfg.exposed, notes):
                log.info(ln)
        except Exception:
            log.exception("discovery failed")
            return
        try:
            ch = self.t.find_channel(self.cfg.agents_channel)
            state.save_state(bot_id=me.agent_id, agents_channel_id=ch)
            who = CardIdentity(
                self.cfg.agent_name, self.cfg.description, self.cfg.owner, me.agent_id, me.handle
            )
            card = build_card(who, caps, self.cfg.exposed, self.cfg.tags)
            if upd := sync_card(self.t, state.load_state(), card, notes):
                state.save_state(**upd)
        except Exception:
            log.exception("card step failed")
        try:
            summary = build_summary(caps, self.cfg.exposed, notes)
            if upd := send_summary(self.t, state.load_state(), self.cfg.owner, summary):
                state.save_state(**upd)
        except Exception:
            log.exception("summary step failed")

    def _exposed(self) -> dict:
        try:
            found, _ = collect(self.cfg)
        except Exception:
            log.exception("discovery failed")
            return {}
        return {c.id: c for c in found if state_of(c, self.cfg.exposed) == "exposed"}

    def start(self) -> None:
        me = self.t.whoami()
        self.agent_id, self.handle = me.agent_id, me.handle
        self.publish_capabilities(me)
        if not self.caps:
            self.caps.update(self._exposed())
        state.init_last_seen(f"{time.time():.6f}")
        self.t.on_event(self.on_event)
        self.t.on_reconnect(lambda: self.submit(self.catch_up))
        self.catch_up()


def build(cfg: Config, transport, runtime, scrub_fn, escape_fn, **kw) -> Adapter:
    return Adapter(cfg, transport, runtime, scrub_fn, escape_fn, **kw)


def run_forever(cfg: Config, transport, runtime, scrub_fn, escape_fn, connect: Callable) -> None:
    """I/O only: catch up, then connect Socket Mode and block. Not unit-tested."""
    _setup_log()
    a = build(cfg, transport, runtime, scrub_fn, escape_fn, flows=load_default())
    a.start()  # handlers + first catch-up, before events flow
    a.submit = ThreadPoolExecutor(max_workers=1).submit  # one worker: replies never overlap
    connect()  # each connect fires on_reconnect, so a gap is caught up
    while True:
        time.sleep(3600)
