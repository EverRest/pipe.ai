"""A slow capability: the run holds the step `running`; only its claimant ends it (DQ1)."""

import threading

from fakes import FakeRuntime
from pipe.core.contract import Message, RuntimeFailed, RuntimeOutput
from pipe.core.route import step_status
from thread_kit import TOP, step
from unit.test_stepper import Rig, first_handoff, meta


class HeldRuntime(FakeRuntime):
    """`run` blocks until `release`. Only a thread can wait here, so tests start one."""

    def __init__(self):
        super().__init__()
        self.entered, self.go, self.result = threading.Event(), threading.Event(), None

    def run(self, inp):
        self.inputs.append(inp)
        self.entered.set()
        assert self.go.wait(5)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def release(self, result):
        self.result = result
        self.go.set()


def held(**kw):
    r = Rig(seed=[first_handoff()], **kw)
    r.rt = r.st.rt = HeldRuntime()
    t = threading.Thread(target=r.st.run_step, args=(r.ev(first_handoff()), 0))
    t.start()
    assert r.rt.entered.wait(5)
    r.join = t.join
    return r


def handoffs(r):
    return [p for p in r.posts() if meta(p).get("next")]


def finish(r, result):
    r.rt.release(result)
    r.join(5)
    return r


def test_held_run_stays_running_and_hands_off_nothing():
    r = held()
    assert step_status(r.load("C", TOP), 0) == "running" and not handoffs(r)
    finish(r, RuntimeOutput("review done", artifacts=["https://x/d"]))
    assert step_status(r.load("C", TOP), 0) == "done"
    assert len(handoffs(r)) == 1 and meta(handoffs(r)[0])["artifacts"] == ["https://x/d"]


def test_other_senders_cannot_end_a_held_step():
    r = held()
    other = {"v": 1, "task_id": TOP, "phase": "step", "status": "done", "by": "B2", "hop": 1}
    md = {"event_type": "pipe.task.v1", "event_payload": {**other, "step": 0, "access": "read"}}
    r.ft.messages += [
        Message(
            "C", "1700000900.000000", TOP, "B2", True, "done", "UB", md
        ),  # card, not step agent
        Message("C", "1700000901.000000", TOP, "B9", True, "done", None, md),  # no card
        Message("C", "1700000902.000000", TOP, "U9", False, "done"),  # human
    ]
    assert step_status(r.load("C", TOP), 0) == "running"
    finish(r, RuntimeOutput("ok"))


def test_run_failed_status_gives_run_failed_and_retry():
    r = finish(held(), RuntimeOutput("x", status="failed"))
    u = r.ft.updates[-1]
    assert meta(u)["reason"] == "run_failed" and u["buttons"] and not handoffs(r)


def test_run_failed_with_on_fail_branches_once_without_button():
    plan = {"steps": [{**step("B1"), "on_fail": 2}, step("B2", "cap-2"), step("B1")]}
    r = held(plan=plan)
    finish(r, RuntimeOutput("x", status="failed"))
    assert meta(r.ft.updates[-1])["reason"] == "run_failed" and not r.ft.updates[-1]["buttons"]
    assert [meta(p)["next"]["payload"]["step"] for p in handoffs(r)] == [2]


def test_runtime_error_gives_retry_even_with_on_fail():
    plan = {"steps": [{**step("B1"), "on_fail": 2}, step("B2", "cap-2"), step("B1")]}
    r = held(plan=plan)
    finish(r, RuntimeFailed("exit 1 xoxb-123456789012"))
    u = r.ft.updates[-1]
    assert meta(u)["status"] == "failed" and u["buttons"] and not handoffs(r)
    assert "xoxb" not in u["text"] and "xoxb" not in str(meta(u))


def test_timeout_gives_failed_timeout_and_retry():
    r = finish(held(), RuntimeFailed("timeout"))
    u = r.ft.updates[-1]
    assert meta(u)["reason"] == "timeout" and u["buttons"]


def test_retry_starts_a_new_claim():
    r = finish(held(), RuntimeFailed("timeout"))
    failed = next(m for m in r.ft.messages if m.metadata and meta(m).get("status") == "failed")
    r.rt = r.st.rt = FakeRuntime()
    r.st.retry_step(failed, 0)
    assert len(r.rt.inputs) == 1 and step_status(r.load("C", TOP), 0) == "done"
