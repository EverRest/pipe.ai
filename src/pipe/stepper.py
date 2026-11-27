"""Step state machine over an injected transport and runtime. No chat or tool names here.
Status texts come from `core/render.py`. The thread is the state: every call re-reads it."""

import shutil
import time
from pathlib import Path
from types import SimpleNamespace

from pipe.core.capability import Capability
from pipe.core.claim import resolve_claim, ts_key
from pipe.core.context import effective_payload
from pipe.core.contract import Button, RuntimeFailed, RuntimeInput, UploadRefused
from pipe.core.gate import gate_decision, gate_required, gate_text, in_allowlist
from pipe.core.pipeline import Step, access_fits, matches_tag, validate_plan
from pipe.core.render import render_step, render_stop, render_trigger
from pipe.core.route import TASK_EVENT, UNVERIFIED, View, card_view
from pipe.core.runrequest import build_run_request
from pipe.core.scrub import scrub
from pipe.runtime_select import check_input, check_output

CLAIM_SETTLE_S = 2
OWNER_OFFLINE_AFTER_S = 60
RETRY = [Button("pipe_retry", "Retry")]
GATE = [Button("pipe_accept", "Accept"), Button("pipe_reject", "Reject")]
_TAG = "tag:"


class Stepper:
    def __init__(
        self,
        transport,
        runtime,
        load,
        caps: dict[str, Capability],
        *,
        sleep=time.sleep,
        timer=None,
        settle_s: float = CLAIM_SETTLE_S,
        step_timeout_min: int = 30,
        dialog_timeout_h: int = 24,
        allowlist=(),
    ):
        """`load(channel, thread_ts)` gives a fresh `ThreadState`. `caps` are the exposed
        capabilities of this agent. `timer(seconds, fn)` is an injected factory.
        `allowlist` comes from the config; the owner is the card owner (spec 004)."""
        self.t, self.rt, self.load, self.caps = transport, runtime, load, caps
        self.sleep, self.timer, self.settle_s = sleep, timer, settle_s
        self.step_timeout_min, self.dialog_timeout_h = step_timeout_min, dialog_timeout_h
        self.allowlist = tuple(allowlist)
        self._seen: set[str] = set()

    # --- small helpers
    def _once(self, key: str) -> bool:
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def _clean(self, text: str) -> str:
        return self.t.escape_mentions(scrub(text or ""))

    def _post(self, ts, text, payload, buttons=None) -> str:
        meta = {"event_type": TASK_EVENT, "event_payload": payload}
        return self.t.post_message(ts.channel, text, ts.thread_ts, meta, buttons)

    def _update(self, ts, msg_ts, text, payload, buttons=None):
        meta = {"event_type": TASK_EVENT, "event_payload": payload}
        self.t.update_message(ts.channel, msg_ts, text, meta, buttons)

    def _base(self, ts, i, hop, access) -> dict:
        return {
            "v": 1,
            "task_id": ts.thread_ts,
            "phase": "step",
            "by": ts.self_id,
            "hop": hop,
            "step": i,
            "access": access,
        }

    def _name(self, ts) -> str:
        return (ts.cards.get(ts.self_id) or {}).get("name") or ts.self_id

    def _mentions(self, ts, step) -> str:
        """Mention of the step agent, or of every eligible agent for a tag step."""
        if step["agent"] != "any":
            ids = [step["agent"]]
        else:
            tag = step["capability"][len(_TAG) :]
            ids = sorted(
                k
                for k, c in ts.cards.items()
                if matches_tag(SimpleNamespace(**c), tag, step["access"])
            )
        return " ".join(self.t.mention(ts.cards[a]["bot_user_id"]) for a in ids if a in ts.cards)

    def _handoff_text(self, ts, v, j) -> str:
        s = v.steps[j]
        goal = self._clean(s["goal"])
        return f"{self._mentions(ts, s)} Step {j + 1} of {len(v.steps)} ({s['access']}): {goal}"

    @staticmethod
    def _next(s, j) -> dict:
        return {"agent": s["agent"], "access": s["access"], "payload": {"step": j}}

    def _schedule(self, ts, v, j, hop):
        """Offline timer (fixed agent) or no-claimer timer (tag step)."""
        if self.timer:
            tag = v.steps[j]["agent"] == "any"
            secs = self.step_timeout_min * 60 if tag else OWNER_OFFLINE_AFTER_S
            self.timer(secs, lambda: self.check_unclaimed(ts.thread_ts, j, hop, ts.channel))

    # --- plan start and refusal
    def start_pipeline(self, ts, plan_msg):
        v = View(ts)
        if v.started() or not v.plan or not self._once(f"start:{ts.channel}:{ts.thread_ts}"):
            return
        p = {
            "v": 1,
            "task_id": ts.thread_ts,
            "phase": "plan",
            "status": "done",
            "by": ts.self_id,
            "hop": 1,
            "step": 0,
            "next": self._next(v.steps[0], 0),
        }
        self._post(ts, self._handoff_text(ts, v, 0), p)
        self._schedule(ts, v, 0, 1)

    def accept_plan(self, ts, msg):
        """Owner clicked Accept on a trigger plan: remove the buttons, then start."""
        if View(ts).started():
            return
        self._update(ts, msg.ts, msg.text, msg.metadata["event_payload"], None)
        self.start_pipeline(ts, msg)

    def reject_plan(self, msg):
        """Owner clicked Reject on a trigger plan: `failed`, `rejected`. No retry."""
        ts = self.load(msg.channel, msg.thread)
        if not self._once(f"reject_plan:{msg.channel}:{msg.ts}"):
            return
        p = {**msg.metadata["event_payload"], "status": "failed", "reason": "rejected"}
        name = (ts.cards.get(ts.starter) or {}).get("name") or "trigger"
        text = render_trigger(name, "failed", "rejected", escape=self.t.escape_mentions)
        self._update(ts, msg.ts, text, p, None)

    def refuse(self, ev, reason="hop limit exceeded"):
        ts = self.load(ev.channel, ev.thread_ts)
        if not self._once(f"refuse:{ev.channel}:{ev.ts}"):
            return
        p, nxt = ev.payload, ev.payload["next"]
        out = {
            "v": 1,
            "task_id": ts.thread_ts,
            "phase": "step",
            "status": "failed",
            "by": ts.self_id,
            "hop": p["hop"],
            "step": nxt["payload"]["step"],
            "access": nxt.get("access"),
            "reason": reason,
        }
        self._post(ts, render_stop(reason.endswith(UNVERIFIED)), out)

    # --- claim and run
    def run_step(self, ev, i: int) -> str:
        """Claim step `i` for a handoff, win the contest, run it. Gives the end state."""
        return self._go(self.load(ev.channel, ev.thread_ts), i, ev.payload["hop"])

    def retry_step(self, msg, i: int):
        """A Retry click: a new claim for the same step with the same hop."""
        ts = self.load(msg.channel, msg.thread)
        p = msg.metadata["event_payload"]
        if not self._once(f"retry:{msg.channel}:{msg.ts}"):
            return
        self._update(ts, msg.ts, msg.text, p, None)
        v = View(ts)
        if p.get("reason") == "no_claimer":
            hop = p["hop"]
            pay = {
                "v": 1,
                "task_id": ts.thread_ts,
                "phase": "plan" if i == 0 else "step",
                "status": "done",
                "by": ts.self_id,
                "hop": hop,
                "step": max(i - 1, 0),
                "next": self._next(v.steps[i], i),
            }
            if i:
                pay["artifacts"] = []
            self._post(ts, self._handoff_text(ts, v, i), pay)
            self._schedule(ts, v, i, hop)
            return
        self._go(ts, i, p["hop"])

    def _go(self, ts, i, hop) -> str:
        v = View(ts)
        s, n = v.steps[i], len(v.steps)
        base = self._base(ts, i, hop, s["access"])
        label = self._name(ts)
        line = render_step(i, n, s["access"], label, "claimed", escape=self.t.escape_mentions)
        claim_ts = self._post(ts, line, {**base, "status": "claimed"})
        self.sleep(self.settle_s)
        if not self._wins(ts, i, claim_ts):
            self.t.delete_message(ts.channel, claim_ts)
            return "lost"
        v = View(ts)
        # same rule as _exec: any sender but this agent's own bot counts, bots too
        humans = [m.sender_id for m in ts.messages if m.sender_id != ts.self_id]
        step = SimpleNamespace(access=v.steps[i]["access"])
        if gate_required(step, ts.starter, v.owner(ts.self_id), humans):
            return self._gate(ts, v, i, claim_ts, hop)
        return self._exec(ts, i, claim_ts, hop)

    def _sender(self, v, i) -> str | None:
        """Sender of the latest trusted handoff to step `i`; None gives the button."""
        hs = [
            p["by"]
            for _, p in v.base
            if ((p.get("next") or {}).get("payload") or {}).get("step") == i
        ]
        return hs[-1] if hs else None

    def _gate(self, ts, v, i, claim_ts, hop) -> str:
        """Owner gate for a `write` step of another person: run now or ask the owner."""
        s, n = v.steps[i], len(v.steps)
        base = self._base(ts, i, hop, s["access"])
        owner = v.owner(ts.self_id)  # card owner, same source as the click check
        if not owner:
            return self._fail(ts, v, i, claim_ts, base, "no owner", buttons=None)
        sender = self._sender(v, i)
        card = ts.cards.get(sender) or {}
        who = gate_decision(sender or "", ts.starter, card.get("owner"), self.allowlist)
        # "auto" also needs every sender in the thread (bots too) to be the owner or allowlisted
        senders = {m.sender_id for m in ts.messages if m.sender_id != ts.self_id}
        if who == "auto" and all(h == owner or in_allowlist(self.allowlist, h) for h in senders):
            return self._exec(ts, i, claim_ts, hop)
        name = lambda x: self._clean((x or {}).get("name") or "agent")  # noqa: E731
        me = ts.cards.get(ts.self_id)
        text = gate_text(i + 1, n, name(me), owner, name(card))
        self._update(ts, claim_ts, text, {**base, "status": "needs_approval"}, GATE)
        return "needs_approval"

    def accept_step(self, msg) -> str:
        """Owner clicked Accept: run the step. Acts only while the gate waits."""
        ts, v, i = self._pending(msg, "accept")
        return self._exec(ts, i, msg.ts, v.last(i)[1]["hop"]) if v else "stale"

    def reject_step(self, msg) -> str:
        """Owner clicked Reject: the step ends `failed`, `rejected`. No retry button."""
        ts, v, i = self._pending(msg, "reject")
        if not v:
            return "stale"
        base = self._base(ts, i, v.last(i)[1]["hop"], "write")
        return self._fail(ts, v, i, msg.ts, base, "rejected", buttons=None)

    def _pending(self, msg, kind):
        ts = self.load(msg.channel, msg.thread)
        v, i = View(ts), msg.metadata["event_payload"].get("step")
        if not (isinstance(i, int) and v.owner_gate_pending(i) and v.last(i)[0].ts == msg.ts):
            return ts, None, i
        return (ts, v, i) if self._once(f"{kind}:{msg.channel}:{msg.ts}") else (ts, None, i)

    def _wins(self, ts, i, claim_ts) -> bool:
        v = View(self.load(ts.channel, ts.thread_ts))
        objs = [SimpleNamespace(ts=m.ts, by=p["by"], status=p["status"]) for m, p in v.claims[i]]
        w = resolve_claim(objs)
        return bool(w and w.ts == claim_ts)

    def _bind(self, s) -> str | None:
        """Tag step: the lowest exposed capability id that has the tag and fits the access."""
        tag = s["capability"][len(_TAG) :]
        ids = sorted(
            k for k, c in self.caps.items() if tag in c.tags and access_fits(s["access"], c.access)
        )
        return ids[0] if ids else None

    def _results(self, v, i) -> list[dict]:
        """Text and links of the done steps before `i`. Claim messages carry no `artifacts`."""
        out: dict[int, dict] = {}
        # Only messages of the agent that the plan assigns to step j.
        for j, msgs in v.msgs.items():
            for m, p in msgs:
                if p["status"] != "done" or "artifacts" not in p or p["by"] != v.agent[j]:
                    continue
                if j < i and j not in out:
                    lines = m.text.split("\n")
                    text = "\n".join(lines[:-1] if p.get("next") else lines)
                    out[j] = {"step": j, "text": text, "artifacts": list(p["artifacts"])}
        return [out[j] for j in sorted(out)]

    def _fail(self, ts, v, i, claim_ts, base, reason, buttons=RETRY, detail=None):
        reason = scrub(reason)[:200]
        text = render_step(
            i,
            len(v.steps),
            base["access"],
            self._name(ts),
            "failed",
            reason,
            escape=self.t.escape_mentions,
        )
        if detail:
            text += "\n" + self._clean(detail)
        self._update(ts, claim_ts, text, {**base, "status": "failed", "reason": reason}, buttons)
        return "failed"

    def _exec(self, ts, i, claim_ts, hop) -> str:
        """Everything after the claim: input check, run, outcome. Also used by a resume."""
        v = View(ts)
        s, n = v.steps[i], len(v.steps)
        base = self._base(ts, i, hop, s["access"])
        fail = lambda reason, **kw: self._fail(ts, v, i, claim_ts, base, reason, **kw)  # noqa: E731
        cap_id = self._bind(s) if s["agent"] == "any" else s.get("capability")
        cap = self.caps.get(cap_id)
        if cap is None:
            return fail("capability not available")
        payload = effective_payload(s.get("payload"), self._results(v, i))
        err = check_input(payload, cap.input_schema)
        if err:
            return fail(err[0])
        step = Step(ts.self_id, s["access"], s["goal"], cap_id, payload, s.get("target"))
        owner = (ts.cards.get(ts.self_id) or {}).get("owner")
        # trust only the owner and this agent's own bot in the thread
        owner_ok = bool(owner) and ts.starter == owner
        owner_ok = owner_ok and all(m.sender_id in (ts.self_id, owner) for m in ts.messages)
        try:
            starter = ts.starter if owner_ok else None
            req = build_run_request(step, starter, owner, cap.output_schema)
        except ValueError:
            return fail("unsupported access")
        label = self._name(ts)
        esc = self.t.escape_mentions
        running = render_step(i, n, s["access"], label, "running", escape=esc)
        self._update(ts, claim_ts, running, {**base, "status": "running"})
        thread = [
            {"user": m.sender_id, "text": m.text}
            for m in sorted(ts.messages, key=lambda m: ts_key(m.ts))
        ]
        task = {
            "id": ts.thread_ts,
            "purpose": "step",
            "step": i,
            "pipeline": {"goal": s["goal"]},
            "payload": payload,
        }
        try:
            out = self.rt.run(RuntimeInput(thread, task, req.requester_is_owner, req))
        except RuntimeFailed as e:
            return fail(str(e) or "runtime failed")
        except LookupError:
            return fail("capability not available")
        if out.status == "waiting" and out.reason == "needs_input":
            return self._ask(ts, v, i, claim_ts, base, out.text)
        if out.status == "failed":
            if s.get("on_fail") is not None:
                return self._branch(ts, v, i, claim_ts, base)
            return fail("run_failed")
        if out.status != "done":  # also `delegate`: it starts nothing
            return fail(f"runtime status {out.status}")
        err = check_output(out, cap.output_schema)
        if err:
            return fail(err[0])
        if not self._wins(ts, i, claim_ts):  # last check before the result post
            self.t.delete_message(ts.channel, claim_ts)
            return "lost"
        reply = self._clean(out.text)
        arts = [scrub(a) for a in out.artifacts if isinstance(a, str) and a.startswith("https://")]
        try:  # only the confined paths of an exec output; a plain output has none
            files = getattr(out, "files", ())
            arts += self.upload_run_files(ts.channel, ts.thread_ts, files, s["goal"])
        except UploadRefused:
            return fail("upload refused")
        finally:  # ponytail: an early return before this point leaves the run dir behind
            if run_dir := getattr(out, "run_dir", None):
                shutil.rmtree(run_dir, ignore_errors=True)
        gate = s.get("gate") == "approval"
        extra = {}
        if out.proposal is not None:
            errs = validate_plan(out.proposal, card_view(ts.cards), ts.starter)
            if errs:
                return fail("invalid_proposal", detail="; ".join(errs))
            extra, gate = {"pipeline": out.proposal}, True
        done = render_step(i, n, s["access"], label, "done", escape=esc)
        self._update(ts, claim_ts, done, {**base, "status": "done"})
        if gate:
            text = (
                reply + "\n" + render_step(i, n, s["access"], label, "needs_approval", escape=esc)
            )
            p = {**base, "status": "needs_approval", "artifacts": arts, **extra}
            self._post(ts, text, p)
            return "needs_approval"
        self._result(ts, v, i, base, reply, arts)
        return "done"

    def upload_run_files(self, channel, thread, files, goal) -> list[str]:
        """Upload each file of a run through the transport; give the links. Raises UploadRefused."""
        title = scrub(goal)
        return [self.t.upload_file(channel, thread, Path(f).name, Path(f), title) for f in files]

    def _result(self, ts, v, i, base, reply, arts):
        """Post the result of step `i`: the final message, an approval request, or a handoff."""
        n, hop = len(v.steps), base["hop"]
        nxt = i + 1 if i + 1 < n else None
        if nxt is not None and any(st.get("on_fail") == nxt for st in v.steps):
            nxt = None  # the branch step is skipped on success
        if nxt is None:
            self._post(ts, reply, {**base, "status": "done", "artifacts": arts})
            return
        s = v.steps[nxt]
        if s["agent"].startswith("human:"):
            user = self.t.mention(s["agent"][6:])
            text = f"{reply}\n{user} Approve step {nxt + 1} of {n}: {self._clean(s['goal'])}"
            p = {
                **base,
                "status": "needs_approval",
                "step": nxt,
                "access": "approve",
                "artifacts": arts,
            }
            self._post(ts, text, p, [Button("pipe_approve", "Approve")])
            return
        p = {
            **base,
            "status": "done",
            "hop": hop + 1,
            "artifacts": arts,
            "next": self._next(s, nxt),
        }
        self._post(ts, f"{reply}\n{self._handoff_text(ts, v, nxt)}", p)
        self._schedule(ts, v, nxt, hop + 1)

    def _branch(self, ts, v, i, claim_ts, base):
        """The step ended `run_failed` and has `on_fail`: hand over to the branch step."""
        j, s = v.steps[i]["on_fail"], v.steps[v.steps[i]["on_fail"]]
        failed = {**base, "status": "failed", "reason": "run_failed"}
        text = render_step(
            i,
            len(v.steps),
            base["access"],
            self._name(ts),
            "failed",
            "run_failed",
            escape=self.t.escape_mentions,
        )
        self._update(ts, claim_ts, text, failed, None)
        line = f"{text} {self._handoff_text(ts, v, j)}".replace(
            f"Step {j + 1}", "Branch: step " + str(j + 1), 1
        )
        self._post(ts, line, {**failed, "hop": base["hop"] + 1, "next": self._next(s, j)})
        self._schedule(ts, v, j, base["hop"] + 1)
        return "branched"

    # --- dialog
    def _ask(self, ts, v, i, claim_ts, base, question):
        n, s = len(v.steps), v.steps[i]
        head = render_step(
            i, n, s["access"], self._name(ts), "waiting", escape=self.t.escape_mentions
        )
        who = self.t.mention(ts.starter) + " " if ts.starter else ""
        me = self.t.mention(ts.self_handle)
        ask = f"{self._clean(question)} Answer in this thread and mention {me}."
        text = f"{who}{head} for input. {ask}"
        self._update(ts, claim_ts, text, {**base, "status": "waiting", "reason": "needs_input"})
        if self.timer:
            self.timer(
                self.dialog_timeout_h * 3600,
                lambda: self.expire_dialog(ts.thread_ts, claim_ts, ts.channel),
            )
        return "waiting"

    def _question(self, channel, thread, ts_):
        ts = self.load(channel, thread)
        q = View(ts).question()
        return (ts, q) if q and q[0].ts == ts_ else (ts, None)

    def resume_step(self, q_msg, reply=None) -> str:
        """Run the same step again after a valid answer. No claim, no hop change."""
        ts, q = self._question(q_msg.channel, q_msg.thread, q_msg.ts)
        if not q:
            return "stale"
        p = q[1]
        return self._exec(ts, p["step"], q[0].ts, p["hop"])

    def expire_dialog(self, thread_ts, ts_, channel=None):
        ts, q = self._question(channel or self.t.find_channel("pipe-work"), thread_ts, ts_)
        if q:
            p = q[1]
            base = self._base(ts, p["step"], p["hop"], p["access"])
            self._fail(ts, View(ts), p["step"], ts_, base, "dialog_timeout")

    # --- other messages
    def approve_step(self, msg):
        ts = self.load(msg.channel, msg.thread)
        v, p = View(ts), msg.metadata["event_payload"]
        cur = v.last(p["step"])
        if not (cur and cur[0].ts == msg.ts and p["status"] == "needs_approval"):
            return
        if not self._once(f"approve:{msg.channel}:{msg.ts}"):
            return
        text = render_step(
            p["step"],
            len(v.steps),
            "approve",
            v.steps[p["step"]]["agent"],
            "done",
            escape=self.t.escape_mentions,
        )
        self._update(ts, msg.ts, text, {**p, "status": "done"}, None)

    def release_step(self, msg):
        """A gate release: post what the step would have posted without the gate."""
        ts = self.load(msg.channel, msg.thread)
        v, p = View(ts), msg.metadata["event_payload"]
        i = p["step"]
        cur = v.last(i)
        if not (v.gate_pending(i) and cur[0].ts == msg.ts):
            return
        if not self._once(f"release:{msg.channel}:{msg.ts}"):
            return
        base = {k: p[k] for k in ("v", "task_id", "phase", "by", "hop", "step", "access")}
        self._result(ts, v, i, base, msg.text.rsplit("\n", 1)[0], list(p.get("artifacts") or ()))

    def interrupt(self, msg):
        ts = self.load(msg.channel, msg.thread)
        p = msg.metadata["event_payload"]
        base = {k: p[k] for k in ("v", "task_id", "phase", "by", "hop", "step", "access")}
        self._fail(ts, View(ts), p["step"], msg.ts, base, "interrupted")

    def check_unclaimed(self, thread_ts, i, hop, channel=None):
        """Timer fired: no claim yet. Fixed agent: `owner offline`. Tag step: `no_claimer`."""
        ts = self.load(channel or self.t.find_channel("pipe-work"), thread_ts)
        v = View(ts)
        if any(p["status"] != "failed" for _, p in v.claims[i]) or v.rejected(i):
            return
        s, n = v.steps[i], len(v.steps)
        tag = s["agent"] == "any"
        reason = "no_claimer" if tag else "owner offline"
        label = (
            f"any agent with tag {s['capability'][len(_TAG) :]}"
            if tag
            else (ts.cards.get(s["agent"]) or {}).get("name", s["agent"])
        )
        status = "failed" if tag else "waiting"
        text = render_step(i, n, s["access"], label, status, reason, escape=self.t.escape_mentions)
        p = {**self._base(ts, i, hop, s["access"]), "status": status, "reason": reason}
        self._post(ts, text, p, RETRY if tag else None)
