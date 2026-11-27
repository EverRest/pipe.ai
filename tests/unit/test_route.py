from pipe.core.contract import ClickEvent, MentionEvent, ReactionEvent
from pipe.core.route import (
    BotMessage,
    Wake,
    first_agent,
    flow_word,
    mentions,
    route,
    wake_all,
)
from thread_kit import (
    CARDS,
    PLAN,
    TOP,
    USERS,
    claim,
    handoff,
    human,
    plan_msg,
    start_msg,
    state,
    step,
    task,
    ts,
)


def human_ev(text, sender="U9", thread=TOP, ts_="1700000001.000009", **kw):
    return MentionEvent("C", ts_, thread, sender, False, text, **kw)


def bot_ev(m):
    return BotMessage("C", m.ts, TOP, m.sender_id, m.metadata["event_payload"], m.sender_handle)


def react(item, sender="U9", name="white_check_mark"):
    return ReactionEvent("e1", "C", item, sender, name)


def click(item, sender="U9", action="pipe_approve"):
    return ClickEvent("e2", "C", item, sender, action)


def act(ev, st):
    d = route(ev, st)
    return d.action, d.reason


# --- helpers
def test_mentions_and_first_agent():
    assert mentions("<@UB> x <@U1> <@UB> <@UA>") == ["UB", "U1", "UA"]
    assert first_agent("<@U1> <@UB> <@UA>", USERS) == "B2"
    assert first_agent("none", USERS) is None


def test_flow_word():
    assert flow_word("@a add X flow:bugfix now") == "bugfix"
    for t in ("noflow:x", "flow:Bad", "flow:", "flow:" + "a" * 33, "flow:x_y", "flow:ok. x"):
        assert flow_word(t) is None
    assert flow_word("flow:Bad flow:ok") is None  # only the first word counts


# --- human messages
def test_two_agents_plan_for_first_only():
    ev = human_ev("<@UA> <@UB> go", ts_=TOP)
    assert act(ev, state(me="B1")) == ("plan", "")
    assert act(ev, state(me="B2")) == ("ignore", "not_planner")


def test_one_agent_chat_and_thread_reply_chat():
    assert act(human_ev("<@UA> hi", ts_=TOP), state())[0] == "chat"
    assert act(human_ev("<@UA> <@UB> hi", thread=TOP), state(me="B2"))[0] == "chat"


def test_human_ignores():
    assert (
        act(
            human_ev("<@UA> <@UB>", sender="B2", ts_=TOP).__class__(
                "C", TOP, TOP, "B2", True, "<@UA> <@UB>"
            ),
            state(),
        )[0]
        == "ignore"
    )
    assert (
        act(human_ev("<@UA> hi", ts_=TOP, event_id="E1"), state(seen_event_ids=frozenset({"E1"})))[
            0
        ]
        == "ignore"
    )
    assert act(human_ev("hi", ts_=TOP), state())[0] == "ignore"
    assert act(human_ev("<@UA> <@UB>", ts_=TOP), state([plan_msg()])) == (
        "ignore",
        "already_planned",
    )


def test_flow_word_plan_flow():
    ev = human_ev("<@UA> go flow:bugfix", ts_=TOP)
    d = route(ev, state())
    assert (d.action, d.arg) == ("plan_flow", "bugfix")
    assert act(human_ev("<@UA> <@UB> flow:x", ts_=TOP), state(me="B2")) == ("ignore", "not_planner")
    assert act(human_ev("<@UA> flow:x", thread=TOP), state())[0] == "chat"


# --- reactions
def test_check_starts_for_starter_and_planner_owner():
    st = state([plan_msg()])
    assert route(react(ts(1)), st).action == "start"
    assert route(react(ts(1), "OA"), st).action == "start"
    assert act(react(ts(1), "U77"), st) == ("ignore", "not_allowed")
    assert act(react(ts(1), name="eyes"), st)[0] == "ignore"
    assert act(react(ts(1)), state([plan_msg(), start_msg()])) == ("ignore", "already_started")
    assert act(react(ts(1)), state([plan_msg()], me="B2"))[0] == "ignore"  # plan of another agent
    assert act(react(ts(1)), state([plan_msg(status="failed", plan=None)]))[0] == "ignore"
    assert act(react("999.1"), state())[0] == "ignore"


def test_untrusted_plan_is_no_target():
    bad = plan_msg(by="B9")  # no card
    assert act(react(bad.ts), state([bad]))[0] == "ignore"
    forged = plan_msg(by="B2")  # a card, but the planner is B1
    assert act(react(forged.ts), state([forged], me="B2"))[0] == "ignore"


# --- bot messages
def test_start_handoff_claim():
    st = state([plan_msg(), start_msg()])
    assert act(bot_ev(start_msg()), st) == ("claim", "")


def test_no_card_and_bad_payload():
    m = handoff(3, "B9", "B1", 1, 0, 2)
    assert act(bot_ev(m), state([plan_msg(), m])) == ("ignore", "no_card")
    ev = BotMessage("C", ts(3), TOP, "B1", {"v": 2}, "UA")
    assert act(ev, state([plan_msg()])) == ("ignore", "bad_payload")
    p = dict(start_msg().metadata["event_payload"], by="B2")
    assert act(BotMessage("C", ts(2), TOP, "B1", p, "UA"), state([plan_msg()])) == (
        "ignore",
        "by_mismatch",
    )


def chain(hop):
    """Plan A,B,A,B,A... the handoff to B2 at step 1 carries `hop`."""
    steps = [step("B1"), step("B2", "cap-2")]
    plan = {"steps": steps, "source": "free"}
    return plan, [
        plan_msg(plan=plan),
        start_msg(),
        claim(3, "B1", 0, "done"),
        handoff(4, "B1", "B2", 1, 0, hop),
    ]


def test_hop_limit_free():
    plan, msgs = chain(3)
    assert act(bot_ev(msgs[-1]), state(msgs, me="B2")) == ("claim", "")
    plan, msgs = chain(4)
    d = route(bot_ev(msgs[-1]), state(msgs, me="B2"))
    assert (d.action, d.reason) == ("refuse", "hop limit exceeded")


def test_hop_4_from_untrusted_is_not_refused():
    plan, msgs = chain(4)
    msgs[-1] = handoff(4, "B9", "B2", 1, 0, 4)
    assert act(bot_ev(msgs[-1]), state(msgs, me="B2")) == ("ignore", "no_card")


class Flow:
    def __init__(self, hash_, ok=True):
        self.hash, self.ok = hash_, ok

    def matches(self, steps, cards, starter):
        return self.ok


H = "a" * 32


def tmpl_chain(hop, flows):
    plan = {"steps": [step("B1"), step("B2", "cap-2")], "source": f"template:t@{H}"}
    msgs = [
        plan_msg(plan=plan),
        start_msg(),
        claim(3, "B1", 0, "done"),
        handoff(4, "B1", "B2", 1, 0, hop),
    ]
    return state(msgs, me="B2", flows=flows), msgs[-1]


def test_template_limit_is_five_when_verified():
    for hop, want in ((4, "claim"), (5, "claim"), (6, "refuse")):
        st, m = tmpl_chain(hop, {"t": Flow(H)})
        assert route(bot_ev(m), st).action == want


def test_unverified_template_refuses_at_4_with_suffix():
    for flows in ({}, {"t": Flow("b" * 32)}, {"t": Flow(H, ok=False)}):
        st, m = tmpl_chain(4, flows)
        d = route(bot_ev(m), st)
        assert (d.action, d.reason) == ("refuse", "hop limit exceeded (plan source not verified)")


def test_not_for_me_not_assigned_not_planner_access():
    _, msgs = chain(2)
    ev = bot_ev(msgs[-1])
    assert act(ev, state(msgs, me="B1")) == ("ignore", "not_for_me")
    assert act(ev, state(msgs, me="B3")) == ("ignore", "not_for_me")
    wrong = handoff(4, "B1", "B3", 1, 0, 2)  # plan assigns step 1 to B2, not B3
    assert act(bot_ev(wrong), state([*msgs[:3], wrong], me="B3")) == ("ignore", "not_assigned")
    wr = {"steps": [step("B1"), {**step("B2", "cap-2"), "access": "approve"}], "source": "free"}
    m2 = [
        plan_msg(plan=wr),
        start_msg(),
        claim(3, "B1", 0, "done"),
        handoff(4, "B1", "B2", 1, 0, 2),
    ]
    assert act(bot_ev(m2[-1]), state(m2, me="B2")) == ("ignore", "unsupported_access")
    forged = plan_msg(1, "B2", PLAN)  # not the planner
    assert act(bot_ev(start_msg()), state([forged, start_msg()])) == ("ignore", "not_planner")


def test_next_access_comes_from_plan_not_message():
    _, msgs = chain(2)
    p = dict(msgs[-1].metadata["event_payload"])
    p["next"] = {**p["next"], "access": "write"}
    ev = BotMessage("C", msgs[-1].ts, TOP, "B1", p, "UA")
    assert act(ev, state(msgs, me="B2")) == ("ignore", "unsupported_access")


def test_already_claimed_and_in_flight():
    _, msgs = chain(2)
    st = state([*msgs, claim(5, "B2", 1)], me="B2")
    assert act(bot_ev(msgs[3]), st) == ("ignore", "already_claimed")
    st = state(msgs, me="B2", in_flight=frozenset({f"step:C:{TOP}:1"}))
    assert act(bot_ev(msgs[3]), st) == ("ignore", "already_claimed")


def test_handoff_must_follow_the_step_chain():
    _, msgs = chain(2)
    skip = handoff(4, "B1", "B2", 1, 0, 2)
    p = dict(skip.metadata["event_payload"], step=1)  # claims to come from step 1, not step 0
    assert act(BotMessage("C", skip.ts, TOP, "B1", p, "UA"), state(msgs, me="B2"))[0] == "ignore"


def test_refused_thread_stops():
    _, msgs = chain(4)
    refusal = claim(5, "B2", 1, "failed", 4, reason="hop limit exceeded")
    assert act(bot_ev(msgs[-1]), state([*msgs, refusal], me="B2")) == ("ignore", "already_refused")


# --- tag steps, exclusion, rejected
TAG = {"steps": [step("B1"), step("any", "tag:review", exclude_agents_of=[0])], "source": "free"}


def tag_state(me, extra=()):
    msgs = [
        plan_msg(plan=TAG),
        start_msg(),
        claim(3, "B1", 0, "done"),
        handoff(4, "B1", "any", 1, 0, 2),
        *extra,
    ]
    return state(msgs, me=me), msgs[3]


def test_tag_step_eligible_and_not():
    st, m = tag_state("B2")
    assert act(bot_ev(m), st) == ("claim", "")
    st, m = tag_state("B3")
    assert act(bot_ev(m), st) == ("ignore", "not_eligible")
    plan, msgs = chain(2)
    fixed = handoff(4, "B1", "any", 1, 0, 2)
    assert act(bot_ev(fixed), state([*msgs[:3], fixed], me="B2")) == ("ignore", "not_assigned")


def test_tag_hop_4_refuses_only_eligible():
    plan = TAG
    msgs = [
        plan_msg(plan=plan),
        start_msg(),
        claim(3, "B1", 0, "done"),
        handoff(4, "B1", "any", 1, 0, 4),
    ]
    assert route(bot_ev(msgs[-1]), state(msgs, me="B2")).action == "refuse"
    assert act(bot_ev(msgs[-1]), state(msgs, me="B3")) == ("ignore", "not_eligible")


def test_exclusion_blocks_the_holder():
    st, m = tag_state("B1")
    assert act(bot_ev(m), st) == ("ignore", "excluded")


def test_rejected_write_tag_step_has_no_second_claimer():
    st, m = tag_state("B2", [claim(5, "B2", 1, "failed", 2, reason="rejected")])
    assert act(bot_ev(m), st) == ("ignore", "rejected")


def test_loser_claim_is_not_the_step_agent():
    # B2 wins (lowest ts); a result from B3 is dropped, so B3 cannot hijack the step.
    plan = {"steps": [step("B1"), step("any", "tag:review"), step("B1")], "source": "free"}
    msgs = [
        plan_msg(plan=plan),
        start_msg(),
        claim(3, "B1", 0, "done"),
        handoff(4, "B1", "any", 1, 0, 2),
        claim(5, "B2", 1),
        claim(6, "B3", 1, "done"),
    ]
    from pipe.core.route import step_agent

    assert step_agent(state(msgs), 1) == "B2"


# --- clicks
def approve_state(me="B2", sender_card=None):
    plan = {"steps": [step("B1"), human("U5")], "source": "free"}
    ask = task(4, "B1", "step", "needs_approval", 2, step=1, access="approve", artifacts=[])
    msgs = [plan_msg(plan=plan), start_msg(), claim(3, "B1", 0, "done"), ask]
    return state(msgs, me="B1"), ask


def test_approve_click():
    st, ask = approve_state()
    assert route(click(ask.ts, "U9"), st).action == "approve"
    assert route(click(ask.ts, "OA"), st).action == "approve"
    assert act(click(ask.ts, "U5"), st) == ("ignore", "not_allowed")  # the named human
    assert act(click(ask.ts, "U9", "x"), st)[0] == "ignore"
    assert act(click("999.1", "U9"), st)[0] == "ignore"
    done = task(5, "B1", "step", "done", 2, step=1, access="approve", artifacts=[])
    st2 = state([*st.messages[1:], done], me="B1")
    assert act(click(ask.ts, "U9"), st2)[0] == "ignore"


def failed_state(**kw):
    msgs = [plan_msg(), start_msg(), claim(3, "B1", 0, "failed", reason="timeout", **kw)]
    return state(msgs), msgs[-1]


def test_retry_click():
    st, f = failed_state()
    d = route(click(f.ts, "U9", "pipe_retry"), st)
    assert (d.action, d.arg[1]) == ("retry", 0)
    assert route(click(f.ts, "OA", "pipe_retry"), st).action == "retry"
    assert act(click(f.ts, "U77", "pipe_retry"), st) == ("ignore", "not_allowed")


def test_retry_after_branch_or_reject_is_ignored():
    plan = {"steps": [step("B1", on_fail=1), step("B2", "cap-2")], "source": "free"}
    nxt = {"agent": "B2", "access": "read", "payload": {"step": 1}}
    f = claim(3, "B1", 0, "failed", reason="run_failed")
    br = task(4, "B1", "step", "failed", 2, step=0, access="read", reason="run_failed", next=nxt)
    st = state([plan_msg(plan=plan), start_msg(), f, br])
    assert act(click(f.ts, "U9", "pipe_retry"), st)[0] == "ignore"
    rej = claim(3, "B1", 0, "failed", reason="rejected")
    assert (
        act(click(rej.ts, "U9", "pipe_retry"), state([plan_msg(), start_msg(), rej]))[0] == "ignore"
    )


# --- gate and release
def gate_state(me="B1"):
    g = task(4, "B1", "step", "needs_approval", 1, step=0, access="read", artifacts=[])
    plan = {"steps": [step("B1", gate="approval"), step("B2", "cap-2")], "source": "free"}
    return state([plan_msg(plan=plan), start_msg(), claim(3, "B1", 0, "done"), g], me=me), g


def test_release_gate():
    st, g = gate_state()
    assert route(react(g.ts), st).action == "release"
    assert route(react(g.ts, "OA"), st).action == "release"
    assert act(react(g.ts, "U77"), st) == ("ignore", "not_allowed")
    assert act(react(g.ts), gate_state("B2")[0])[0] == "ignore"
    rel = handoff(5, "B1", "B2", 1, 0, 2)
    assert act(react(g.ts), state([*st.messages[1:], rel]))[0] == "ignore"
    # a proposal never hands off
    prop = task(
        4,
        "B1",
        "step",
        "needs_approval",
        2,
        step=0,
        access="read",
        next={"agent": "B2", "payload": {"step": 1}},
    )
    assert act(react(prop.ts), state([plan_msg(), start_msg(), prop]))[0] == "ignore"


def test_gate_message_is_no_handoff():
    st, g = gate_state()
    assert act(bot_ev(g), st)[0] == "ignore"


# --- dialog
def dialog_state(me="B1"):
    q = task(4, "B1", "step", "waiting", 1, step=0, access="read", reason="needs_input")
    return state([plan_msg(), start_msg(), q], me=me), q


def test_resume_from_starter_or_owner_only():
    st, q = dialog_state()
    ok = human_ev("<@UA> main", thread=TOP)
    d = route(ok, st)
    assert (d.action, d.arg[0].ts) == ("resume", q.ts)
    assert route(human_ev("<@UA> main", "OA", thread=TOP), st).action == "resume"
    assert route(human_ev("<@UA> main", "U77", thread=TOP), st).action == "chat"
    assert act(ok, dialog_state("B2")[0]) == ("ignore", "not_for_me")


def test_reply_for_other_agents_question():
    st, _ = dialog_state(me="B2")
    assert act(human_ev("<@UA> main", thread=TOP), st) == ("ignore", "not_for_me")


def test_after_resume_second_reply_is_chat():
    run = claim(5, "B1", 0, "running")
    st = state(
        [
            plan_msg(),
            start_msg(),
            task(4, "B1", "step", "waiting", 1, step=0, access="read", reason="needs_input"),
            run,
        ]
    )
    assert route(human_ev("<@UA> again", thread=TOP), st).action == "chat"


# --- wake
def test_wake_interrupt_expire_claim_start_plan():
    now = float(ts(9))
    run = claim(3, "B1", 0, "running")
    st = state([plan_msg(), start_msg(), run])
    assert [d.action for d in wake_all(Wake(TOP, now), st)] == ["interrupt"]
    busy = state([plan_msg(), start_msg(), run], in_flight=frozenset({f"step:C:{TOP}:0"}))
    assert wake_all(Wake(TOP, now), busy) == []
    assert wake_all(Wake(TOP, now), state([plan_msg(), start_msg(), run], me="B2")) == []
    q = task(3, "B1", "step", "waiting", 1, step=0, access="read", reason="needs_input")
    stq = state([plan_msg(), start_msg(), q])
    assert wake_all(Wake(TOP, float(ts(3)) + 3600), stq) == []  # waiting is not interrupted
    assert [d.action for d in wake_all(Wake(TOP, float(ts(3)) + 24 * 3600 + 60), stq)] == [
        "expire_dialog"
    ]
    assert [d.action for d in wake_all(Wake(TOP, now), state([plan_msg(), start_msg()]))] == [
        "claim"
    ]
    assert [d.action for d in wake_all(Wake(TOP, now), state())] == ["plan"]
    assert wake_all(Wake(TOP, now), state(me="B2")) == []


def test_wake_start_for_missed_check():
    p = plan_msg()
    p = type(p)(**{**p.__dict__, "reactions": [{"name": "white_check_mark", "users": ["U9"]}]})
    assert [d.action for d in wake_all(Wake(TOP, 1e10), state([p]))] == ["start"]
    other = type(p)(**{**p.__dict__, "reactions": [{"name": "white_check_mark", "users": ["U5"]}]})
    assert wake_all(Wake(TOP, 1e10), state([other])) == []


def test_wake_claims_open_handoff_once():
    _, msgs = chain(2)
    assert [d.action for d in wake_all(Wake(TOP, 1e10), state(msgs, me="B2"))] == ["claim"]
    st = state([*msgs, claim(5, "B2", 1)], me="B2")
    assert wake_all(Wake(TOP, 1e10), st) == [] or all(
        d.action != "claim" for d in wake_all(Wake(TOP, 1e10), st)
    )


def test_rejected_step_gives_no_claim_on_wake():
    plan = {"steps": [step("B3", "cap-3"), step("any", "tag:review")], "source": "free"}
    msgs = [
        plan_msg(plan=plan),
        start_msg(agent="B3"),
        claim(3, "B3", 0, "done"),
        handoff(4, "B3", "any", 1, 0, 2),
        claim(5, "B1", 1, "failed", 2, reason="rejected"),
    ]
    assert wake_all(Wake(TOP, 1e10), state(msgs, me="B2")) == []
    assert act(bot_ev(msgs[3]), state(msgs, me="B2")) == ("ignore", "rejected")


def test_card_data_unchanged():
    assert CARDS["B1"]["owner"] == "OA"


def test_step_status_is_latest_trusted_by_numeric_ts():
    from dataclasses import replace

    from pipe.core.route import step_status
    from thread_kit import task as _task

    assert step_status(state([plan_msg()]), 0) == "pending"  # a plan is no step message
    old = replace(_task(9, "B1", "step", "claimed", 1, step=0), ts="999.000000")
    new = replace(_task(10, "B1", "step", "done", 1, step=0), ts="1000.000000")
    assert step_status(state([plan_msg(), new, old]), 0) == "done"  # 999 < 1000 as numbers
    forged = _task(11, "B9", "step", "failed", 1, step=0)
    assert step_status(state([plan_msg(), old, forged]), 0) == "claimed"  # no card: ignored
