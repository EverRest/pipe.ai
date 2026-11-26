"""Composition root and main loop. Imports no Slack module (FR-020)."""

import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from pipe import state
from pipe.config import Config
from pipe.core.catchup import parents_to_scan, pick_missed
from pipe.core.contract import MentionEvent, Message, RuntimeFailed, RuntimeInput
from pipe.core.dedupe import remember
from pipe.core.router import is_owner, should_handle
from pipe.core.status import parse_status_messages, recent, render_summary

WEEK = 7 * 86400
log = logging.getLogger("pipe.adapter")


def _setup_log() -> None:
    p = state.pipe_home() / "logs" / "adapter.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=p, level=logging.INFO, format="%(asctime)s %(message)s")


class Adapter:
    def __init__(self, cfg: Config, transport, runtime, scrub_fn: Callable, escape_fn: Callable):
        self.cfg, self.t, self.rt = cfg, transport, runtime
        self.scrub, self.esc = scrub_fn, escape_fn
        seen = state.load_seen()
        self.event_ids, self.keys = seen["event_ids"], seen["mention_keys"]
        self.in_flight: set[str] = set()
        self.submit: Callable = lambda f, *a: f(*a)  # run_forever swaps in one worker thread
        self.agent_id = ""

    def _safe(self, text: str) -> str:
        return self.esc(self.scrub(text))

    # Receipt: decide, then mark in flight (memory only).
    def _accept(self, e: MentionEvent):
        d = should_handle(
            e, self.agent_id, self.t.mention, self.event_ids, self.keys, self.in_flight
        )
        if d.action == "ignore":
            return None
        self.in_flight.update({f"{e.channel}:{e.ts}", *([e.event_id] if e.event_id else [])})
        return d

    def on_event(self, e) -> None:
        if isinstance(e, MentionEvent) and (d := self._accept(e)):
            self.submit(self._process, e, d.action)

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
        thread = [
            {"user": m.sender_handle or m.sender_id, "text": m.text}
            for m in self.t.replies(e.channel, e.thread_ts)
        ]
        inp = RuntimeInput(
            thread,
            {"id": uuid.uuid4().hex, "purpose": "chat"},
            is_owner(e.sender_id, self.cfg.owner),
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

    def start(self) -> None:
        self.agent_id = self.t.whoami().agent_id
        state.init_last_seen(f"{time.time():.6f}")
        self.t.on_event(self.on_event)
        self.t.on_reconnect(lambda: self.submit(self.catch_up))
        self.catch_up()


def build(cfg: Config, transport, runtime, scrub_fn: Callable, escape_fn: Callable) -> Adapter:
    return Adapter(cfg, transport, runtime, scrub_fn, escape_fn)


def run_forever(cfg: Config, transport, runtime, scrub_fn, escape_fn, connect: Callable) -> None:
    """I/O only: catch up, then connect Socket Mode and block. Not unit-tested."""
    _setup_log()
    a = build(cfg, transport, runtime, scrub_fn, escape_fn)
    a.start()  # handlers + first catch-up, before events flow
    a.submit = ThreadPoolExecutor(max_workers=1).submit  # one worker: replies never overlap
    connect()  # each connect fires on_reconnect, so a gap is caught up
    while True:
        time.sleep(3600)
