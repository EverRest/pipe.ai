from fakes import FakeRuntime, FakeTransport
from pipe.core.capability import Capability
from pipe.core.contract import Message, RuntimeOutput
from pipe.core.route import BotMessage
from pipe.stepper import Stepper
from thread_kit import CARDS, PARENT, TOP, claim, handoff, human, plan_msg, start_msg, state, step


def meta(m):
    return m["metadata"]["event_payload"] if isinstance(m, dict) else m.metadata["event_payload"]


class Rig:
    def __init__(self, me="B1", plan=None, seed=(), out=None, error=None, caps=None, **kw):
        self.ft = FakeTransport(me, CARDS[me]["bot_user_id"], {"pipe-work": "C"})
        self.ft._n = 100
        self.ft.add_message("C", PARENT, "U9", ts=TOP)
        self.ft.messages.extend([plan_msg(plan=plan) if plan else plan_msg(), *seed])
        self.rt = FakeRuntime(out, error)
        self.me, self.slept = me, []
        self.caps = (
            caps
            if caps is not None
            else {
                "cap-1": Capability("cap-1", "n1", tags=("review",)),
                "cap-2": Capability("cap-2", "n2", tags=("review",)),
            }
        )
        self.sleeps = []
        self.st = Stepper(self.ft, self.rt, self.load, self.caps, sleep=self.sleep, **kw)

    def sleep(self, s):
        self.slept.append(s)
        for f in self.sleeps:
            f()

    def load(self, channel, thread):
        msgs = tuple(m for m in self.ft.messages if m.thread == TOP)
        return state(msgs, me=self.me)

    def ev(self, m):
        return BotMessage("C", m.ts, TOP, m.sender_id, meta(m), m.sender_handle)

    def posts(self):
        return [p for p in self.ft.posts if p["metadata"]]

    def last_post(self):
        return self.ft.posts[-1]


def first_handoff(to="B1"):
    return start_msg(2, agent=to)


def test_happy_path_posts_claim_running_done_and_handoff():
    r = Rig(seed=[first_handoff()])
    r.st.run_step(r.ev(first_handoff()), 0)
    claim_post = r.ft.posts[0]
    assert claim_post["text"].endswith("claimed")
    assert meta(claim_post)["status"] == "claimed" and meta(claim_post)["hop"] == 1
    assert [u["text"].split(": ")[-1] for u in r.ft.updates] == ["running", "done"]
    out = r.last_post()
    p = meta(out)
    assert (p["status"], p["hop"], p["step"]) == ("done", 2, 0)
    assert p["next"] == {"agent": "B2", "access": "read", "payload": {"step": 1}}
    assert "<@UB>" in out["text"] and "Step 2 of 2" in out["text"]
    assert r.slept == [2]  # CLAIM_SETTLE_S


def test_runtime_gets_plan_goal_and_request_only():
    r = Rig(seed=[first_handoff()])
    r.st.run_step(r.ev(first_handoff()), 0)
    inp = r.rt.inputs[0]
    assert inp.task["step"] == 0 and inp.task["pipeline"] == {"goal": "do it"}
    assert inp.request.capabilities == ("cap-1",) and inp.request.access == "read"
    assert inp.request.requester_is_owner is False  # starter U9 is not the owner OA
    assert "hop" not in str(inp.task) and "OA" not in str(inp.task)
    assert any("do it" in t["text"] for t in inp.thread)


def test_starter_is_owner_gives_owner_request():
    r = Rig(seed=[first_handoff()])
    r.load = lambda c, t: state(
        tuple(m for m in r.ft.messages if m.thread == TOP and m.sender_id != "U9"), starter="OA"
    )
    r.st.load = r.load
    r.st.run_step(r.ev(first_handoff()), 0)
    assert r.rt.inputs[0].request.requester_is_owner is True


def _owner_run(extra=None):
    r = Rig(seed=[first_handoff()])

    def msgs():
        base = tuple(m for m in r.ft.messages if m.thread == TOP and m.sender_id != "U9")
        return base + ((extra,) if extra else ())

    r.st.load = lambda c, t: state(msgs(), starter="OA")
    r.st.run_step(r.ev(first_handoff()), 0)
    return r.rt.inputs[0].request.requester_is_owner


def test_owner_only_thread_gives_owner_request():
    assert _owner_run() is True


def test_other_bot_in_thread_drops_owner_request():
    assert _owner_run(Message("C", "1700000900.000000", TOP, "B2", True, "hi")) is False


def test_non_owner_human_in_thread_drops_owner_request():
    assert _owner_run(Message("C", "1700000900.000000", TOP, "U7", False, "hi")) is False


def test_last_step_posts_final_result_without_next_and_same_hop():
    plan = {"steps": [step("B1")], "source": "free"}
    r = Rig(
        plan=plan,
        seed=[first_handoff()],
        out=RuntimeOutput("all done", artifacts=["https://x.test/mr/1"]),
    )
    r.st.run_step(r.ev(first_handoff()), 0)
    p = meta(r.last_post())
    assert p["status"] == "done" and "next" not in p and p["hop"] == 1
    assert p["artifacts"] == ["https://x.test/mr/1"]


def test_human_last_step_gets_approval_request_with_button():
    plan = {"steps": [step("B1"), human("U9")], "source": "free"}
    r = Rig(plan=plan, seed=[first_handoff()])
    r.st.run_step(r.ev(first_handoff()), 0)
    post = r.last_post()
    p = meta(post)
    assert (p["status"], p["access"], p["step"], p["hop"]) == ("needs_approval", "approve", 1, 1)
    assert [b.action_id for b in post["buttons"]] == ["pipe_approve"]
    assert "<@U9>" in post["text"]


def test_reply_is_scrubbed_and_mentions_escaped():
    r = Rig(
        seed=[first_handoff()], out=RuntimeOutput("hi <@UZ> token xoxb-123456789012-abcdefghij")
    )
    r.st.run_step(r.ev(first_handoff()), 0)
    text = r.last_post()["text"]
    assert "<@UZ>" not in text and "xoxb-" not in text


def test_runtime_failed_gives_retry_button_and_no_branch():
    plan = {"steps": [step("B1", on_fail=1), step("B2", "cap-2")], "source": "free"}
    r = Rig(plan=plan, seed=[first_handoff()], error="timeout")
    r.st.run_step(r.ev(first_handoff()), 0)
    u = r.ft.updates[-1]
    assert meta(u)["status"] == "failed" and meta(u)["reason"] == "timeout"
    assert [b.action_id for b in u["buttons"]] == ["pipe_retry"]
    assert len(r.ft.posts) == 1  # the claim only: no handoff, no branch


def test_run_failed_status_branches_with_hop_plus_one():
    plan = {"steps": [step("B1", on_fail=1), step("B2", "cap-2")], "source": "free"}
    r = Rig(plan=plan, seed=[first_handoff()], out=RuntimeOutput("bad", status="failed"))
    r.st.run_step(r.ev(first_handoff()), 0)
    u, post = r.ft.updates[-1], r.last_post()
    assert not u["buttons"] and meta(u)["reason"] == "run_failed"
    p = meta(post)
    assert (p["status"], p["reason"], p["hop"], p["step"]) == ("failed", "run_failed", 2, 0)
    assert p["next"]["payload"] == {"step": 1} and not post["buttons"]
    assert "<@UB>" in post["text"] and "Branch" in post["text"]


def test_run_failed_without_on_fail_gets_retry():
    r = Rig(seed=[first_handoff()], out=RuntimeOutput("bad", status="failed"))
    r.st.run_step(r.ev(first_handoff()), 0)
    u = r.ft.updates[-1]
    assert meta(u)["reason"] == "run_failed" and [b.action_id for b in u["buttons"]] == [
        "pipe_retry"
    ]


def test_delegate_status_starts_nothing():
    r = Rig(seed=[first_handoff()], out=RuntimeOutput("x", status="delegate", next={"agent": "B3"}))
    r.st.run_step(r.ev(first_handoff()), 0)
    assert meta(r.ft.updates[-1])["reason"] == "runtime status delegate"
    assert len(r.ft.posts) == 1


def test_unknown_capability_fails_before_run():
    r = Rig(seed=[first_handoff()], caps={})
    r.st.run_step(r.ev(first_handoff()), 0)
    assert meta(r.ft.updates[-1])["reason"] == "capability not available"
    assert r.rt.inputs == []


def test_input_schema_checks_effective_payload():
    schema = {"type": "object", "additionalProperties": False, "properties": {}}
    caps = {
        "cap-1": Capability("cap-1", "n", input_schema=schema),
        "cap-2": Capability("cap-2", "n", input_schema=schema),
    }
    r = Rig(seed=[first_handoff()], caps=caps)
    r.st.run_step(r.ev(first_handoff()), 0)  # step 0: no context, passes
    assert len(r.rt.inputs) == 1
    done0 = claim(5, "B1", 0, "done")
    res = handoff(6, "B1", "B2", 1, 0, 2, "result text")
    r2 = Rig("B2", seed=[first_handoff(), done0, res], caps=caps)
    r2.st.run_step(r2.ev(res), 1)  # step 1: context key breaks the schema
    assert meta(r2.ft.updates[-1])["reason"] == "invalid_payload" and r2.rt.inputs == []


def test_invalid_result_fails():
    caps = {"cap-1": Capability("cap-1", "n", output_schema={"type": "object", "required": ["k"]})}
    r = Rig(seed=[first_handoff()], caps=caps, out=RuntimeOutput("x", data={}))
    r.st.run_step(r.ev(first_handoff()), 0)
    assert meta(r.ft.updates[-1])["reason"] == "invalid_result"


def test_next_step_gets_context_of_all_previous_steps():
    plan = {"steps": [step("B1"), step("B2", "cap-2"), step("B1")], "source": "free"}
    d0 = handoff(5, "B1", "B2", 1, 0, 2, "first result\n<@UB> Step 2")
    d0 = type(d0)(
        **{
            **d0.__dict__,
            "metadata": {
                **d0.metadata,
                "event_payload": {**meta(d0), "artifacts": ["https://x.test/1"]},
            },
        }
    )
    d1 = handoff(7, "B2", "B1", 2, 1, 3, "second result\n<@UA> Step 3")
    seed = [
        start_msg(2, agent="B1"),
        claim(3, "B1", 0, "done"),
        d0,
        claim(6, "B2", 1, "done", 2),
        d1,
    ]
    r = Rig("B1", plan=plan, seed=seed)
    r.st.run_step(r.ev(d1), 2)
    pl = r.rt.inputs[0].task["payload"]
    assert [c["text"] for c in pl["context"]] == ["first result", "second result"]
    assert pl["artifacts"] == ["https://x.test/1"]


def test_lost_contest_deletes_claim_and_runs_nothing():
    r = Rig(seed=[first_handoff()])
    low = claim(3, "B1", 0)  # a lower ts claim by the same bot
    r.sleeps.append(lambda: r.ft.messages.append(low))
    r.st.run_step(r.ev(first_handoff()), 0)
    assert r.rt.inputs == [] and len(r.ft.deleted) == 1 and not r.ft.updates


def test_dialog_question_resume_and_expire():
    out = [
        RuntimeOutput("Which branch?", status="waiting", reason="needs_input"),
        RuntimeOutput("ok"),
    ]
    r = Rig(seed=[first_handoff()], out=out[0])
    r.st.run_step(r.ev(first_handoff()), 0)
    q = r.ft.updates[-1]
    assert meta(q)["status"] == "waiting" and meta(q)["reason"] == "needs_input"
    assert "Which branch?" in q["text"] and "<@U9>" in q["text"] and "<@UA>" in q["text"]
    assert len(r.ft.posts) == 1 and len(r.rt.inputs) == 1
    # answer, then resume the same step: no new claim, hop unchanged
    r.ft.add_message("C", "<@UA> main", "U9", thread=TOP)
    r.rt.output = out[1]
    qmsg = next(m for m in r.ft.messages if m.ts == q["ts"])
    r.st.resume_step(qmsg, None)
    r.st.resume_step(qmsg, None)  # second call: no second run
    assert len(r.rt.inputs) == 2 and r.rt.inputs[1].task == r.rt.inputs[0].task
    assert r.rt.inputs[1].request == r.rt.inputs[0].request
    assert any("main" in t["text"] for t in r.rt.inputs[1].thread)
    assert meta(r.last_post())["hop"] == 2
    assert len([p for p in r.ft.posts if p["text"].endswith("claimed")]) == 1


def test_expire_dialog_fails_with_retry_and_runs_nothing():
    r = Rig(seed=[first_handoff()], out=RuntimeOutput("Q?", status="waiting", reason="needs_input"))
    r.st.run_step(r.ev(first_handoff()), 0)
    ts_ = r.ft.updates[-1]["ts"]
    r.st.expire_dialog(TOP, ts_)
    r.st.expire_dialog(TOP, ts_)
    u = r.ft.updates[-1]
    assert meta(u)["reason"] == "dialog_timeout" and [b.action_id for b in u["buttons"]] == [
        "pipe_retry"
    ]
    assert len(r.rt.inputs) == 1 and len(r.ft.updates) == 3  # running, waiting, failed


def test_gate_blocks_handoff_until_release():
    plan = {"steps": [step("B1", gate="approval"), step("B2", "cap-2")], "source": "free"}
    r = Rig(plan=plan, seed=[first_handoff()])
    r.st.run_step(r.ev(first_handoff()), 0)
    g = r.last_post()
    assert meta(g)["status"] == "needs_approval" and "next" not in meta(g)
    gmsg = next(m for m in r.ft.messages if m.ts == g["ts"])
    n = len(r.ft.posts)
    r.st.release_step(gmsg)
    r.st.release_step(gmsg)  # once
    assert len(r.ft.posts) == n + 1 and len(r.rt.inputs) == 1
    p = meta(r.last_post())
    assert p["status"] == "done" and p["hop"] == 2 and p["next"]["payload"] == {"step": 1}


def test_proposal_valid_gates_and_invalid_fails():
    good = {"steps": [step("B2", "cap-2")], "source": "free"}
    r = Rig(seed=[first_handoff()], out=RuntimeOutput("p", proposal=good))
    r.st.run_step(r.ev(first_handoff()), 0)
    p = meta(r.last_post())
    assert p["status"] == "needs_approval" and p["pipeline"] == good and "next" not in p
    bad = {"steps": [step("B9", "cap-9")], "source": "free"}
    r = Rig(seed=[first_handoff()], out=RuntimeOutput("p", proposal=bad))
    r.st.run_step(r.ev(first_handoff()), 0)
    u = r.ft.updates[-1]
    assert meta(u)["reason"] == "invalid_proposal" and [b.action_id for b in u["buttons"]] == [
        "pipe_retry"
    ]
    assert len(r.ft.posts) == 1


def test_tag_step_binds_lowest_exposed_capability():
    plan = {"steps": [step("B3", "cap-3"), step("any", "tag:review")], "source": "free"}
    h = handoff(5, "B3", "any", 1, 0, 2)
    caps = {
        "z": Capability("z", "z", tags=("review",)),
        "a": Capability("a", "a", tags=("review",)),
        "n": Capability("n", "n"),
    }
    r = Rig(
        "B2", plan=plan, seed=[start_msg(2, agent="B3"), claim(3, "B3", 0, "done"), h], caps=caps
    )
    r.st.run_step(r.ev(h), 1)
    assert r.rt.inputs[0].request.capabilities == ("a",)


def test_start_pipeline_posts_type_3_once_and_mentions_every_tag_agent():
    r = Rig()
    plan_m = r.ft.messages[1]
    r.st.start_pipeline(r.load("C", TOP), plan_m)
    r.st.start_pipeline(r.load("C", TOP), plan_m)
    assert len(r.ft.posts) == 1
    p = meta(r.last_post())
    assert (p["phase"], p["status"], p["hop"], p["step"]) == ("plan", "done", 1, 0)
    assert p["next"] == {"agent": "B1", "access": "read", "payload": {"step": 0}}
    assert "<@UA>" in r.last_post()["text"]
    tag = {"steps": [step("any", "tag:review")], "source": "free"}
    r = Rig(plan=tag)
    r.st.start_pipeline(r.load("C", TOP), r.ft.messages[1])
    assert "<@UA>" in r.last_post()["text"] and "<@UB>" in r.last_post()["text"]
    assert "<@UC>" not in r.last_post()["text"]


def test_refuse_posts_once_with_suffix():
    r = Rig("B2", seed=[first_handoff("B2")])
    ev = r.ev(first_handoff("B2"))
    r.st.refuse(ev, "hop limit exceeded (plan source not verified)")
    r.st.refuse(ev, "hop limit exceeded (plan source not verified)")
    assert len(r.ft.posts) == 1
    p = meta(r.last_post())
    assert (p["status"], p["reason"], p["hop"]) == (
        "failed",
        "hop limit exceeded (plan source not verified)",
        1,
    )
    assert r.last_post()["text"] == "Stopped. Reason: hop limit exceeded (plan source not verified)"
    assert r.rt.inputs == []


def test_approve_step_sets_done_once_and_removes_button():
    plan = {"steps": [step("B1"), human("U9")], "source": "free"}
    r = Rig(plan=plan, seed=[first_handoff()])
    r.st.run_step(r.ev(first_handoff()), 0)
    ask = next(m for m in r.ft.messages if m.ts == r.last_post()["ts"])
    r.st.approve_step(ask)
    r.st.approve_step(ask)
    u = r.ft.updates[-1]
    assert meta(u)["status"] == "done" and not u["buttons"] and len(r.ft.updates) == 3


def test_retry_makes_a_new_claim_with_the_same_hop():
    failed = claim(3, "B1", 0, "failed", 2, reason="timeout")
    r = Rig(seed=[first_handoff(), failed])
    r.st.retry_step(failed, 0)
    assert meta(r.ft.posts[0])["hop"] == 2 and meta(r.ft.posts[0])["status"] == "claimed"
    assert r.ft.updates[0]["buttons"] in (None, []) and meta(r.ft.updates[0])["reason"] == "timeout"
    assert len(r.rt.inputs) == 1


def test_interrupt_fails_with_retry_button():
    run = claim(3, "B1", 0, "running")
    r = Rig(seed=[first_handoff(), run])
    r.st.interrupt(run)
    u = r.ft.updates[0]
    assert meta(u)["reason"] == "interrupted" and [b.action_id for b in u["buttons"]] == [
        "pipe_retry"
    ]


def test_unclaimed_fixed_step_waits_owner_offline_and_tag_step_gives_no_claimer():
    h = first_handoff("B2")
    r = Rig("B2", seed=[h])
    r.st.check_unclaimed(TOP, 0, 1)
    p = meta(r.last_post())
    assert (p["status"], p["reason"], p["step"]) == ("waiting", "owner offline", 0)
    r.ft.messages.append(claim(7, "B1", 0))
    n = len(r.ft.posts)
    r.st.check_unclaimed(TOP, 0, 1)
    assert len(r.ft.posts) == n  # a claim exists
    tag = {"steps": [step("any", "tag:review")], "source": "free"}
    r = Rig("B3", plan=tag, seed=[start_msg(2, agent="any")])
    r.st.check_unclaimed(TOP, 0, 1)
    post = r.last_post()
    assert meta(post)["reason"] == "no_claimer" and [b.action_id for b in post["buttons"]] == [
        "pipe_retry"
    ]


def test_write_step_never_runs():
    plan = {"steps": [{**step("B1"), "access": "write"}], "source": "free"}
    h = start_msg(2, agent="B1")
    r = Rig(plan=plan, seed=[h])
    r.st.run_step(r.ev(h), 0)
    assert r.rt.inputs == []
