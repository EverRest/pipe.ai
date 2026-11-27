"""Owner gate (type 4) in `route`: clicks, rejection, kept apart from the type 5 gate."""

from pipe.core.contract import ClickEvent, ReactionEvent
from pipe.core.route import BotMessage, Wake, route, wake_all
from thread_kit import TOP, claim, plan_msg, start_msg, state, step, task

WRITE = {"steps": [step("B1"), {**step("B2", "cap-2"), "access": "write"}], "source": "free"}
TAG = {
    "steps": [step("B1"), {**step("any", "tag:review"), "access": "write"}],
    "source": "free",
}


def handoff_w(n=4, to="B2"):
    nxt = {"agent": to, "access": "write", "payload": {"step": 1}}
    return task(n, "B1", "step", "done", 2, step=0, access="read", next=nxt, artifacts=[])


def gate(n=5, **kw):
    return task(n, "B2", "step", "needs_approval", 2, step=1, access="write", **kw)


def thread(plan=WRITE, *extra):
    return [plan_msg(plan=plan), start_msg(), claim(3, "B1", 0, "done"), handoff_w(), *extra]


def click(m, sender, action="pipe_accept"):
    return ClickEvent("e", "C", m.ts, sender, action)


def act(ev, st):
    d = route(ev, st)
    return d.action, d.reason


def test_owner_accept_and_reject():
    g = gate()
    st = state(thread(WRITE, g), me="B2")
    assert act(click(g, "OB"), st)[0] == "accept"
    assert act(click(g, "OB", "pipe_reject"), st)[0] == "reject"


def test_only_the_owner_may_click():
    g = gate()
    st = state(thread(WRITE, g), me="B2")
    for who in ("U9", "OA", "OC", "B1", ""):  # starter, other owner, bot
        assert act(click(g, who), st)[0] == "ignore"
        assert act(click(g, who, "pipe_reject"), st)[0] == "ignore"


def test_owner_who_started_the_thread_may_click():
    g = gate()
    st = state(thread(WRITE, g), me="B2", starter="OB")
    assert act(click(g, "OB"), st)[0] == "accept"


def test_second_click_changes_nothing():
    g = gate()
    for later in (
        task(6, "B2", "step", "running", 2, step=1, access="write"),
        task(6, "B2", "step", "failed", 2, step=1, access="write", reason="rejected"),
    ):
        st = state(thread(WRITE, g, later), me="B2")
        assert act(click(g, "OB"), st)[0] == "ignore"
        assert act(click(g, "OB", "pipe_reject"), st)[0] == "ignore"


def test_click_on_a_foreign_gate_is_ignored():
    g = gate()
    st = state(thread(WRITE, g), me="B1")
    assert act(click(g, "OB"), st) == ("ignore", "no_target")


def test_type5_gate_is_not_the_owner_gate():
    t5 = task(5, "B2", "step", "needs_approval", 2, step=1, access="write", artifacts=[])
    st = state(thread(WRITE, t5), me="B2")
    assert act(click(t5, "OB"), st)[0] == "ignore"  # no accept on a type 5 gate
    ok = ReactionEvent("r", "C", t5.ts, "U9", "white_check_mark")
    assert act(ok, st)[0] == "release"


def test_check_mark_does_not_release_the_owner_gate():
    g = gate()
    st = state(thread(WRITE, g), me="B2")
    for who in ("U9", "OB"):
        ev = ReactionEvent("r", "C", g.ts, who, "white_check_mark")
        assert act(ev, st)[0] == "ignore"
    g.reactions.append({"name": "white_check_mark", "users": ["U9", "OB"]})
    assert all(d.action != "release" for d in wake_all(Wake(TOP, 9e9), st))


def test_wake_keeps_the_gate_open():
    st = state(thread(WRITE, gate()), me="B2")
    assert all(d.action not in ("interrupt", "claim") for d in wake_all(Wake(TOP, 9e9), st))


def test_write_handoff_is_claimed_and_access_comes_from_plan():
    m = handoff_w()
    st = state(thread(WRITE)[:-1] + [m], me="B2")
    pay = m.metadata["event_payload"]
    assert route(BotMessage("C", m.ts, TOP, "B1", pay, "UA"), st).action == "claim"
    forged = {**pay, "next": {**pay["next"], "access": "read"}}
    ev = BotMessage("C", m.ts, TOP, "B1", forged, "UA")
    assert act(ev, st) == ("ignore", "unsupported_access")


def test_rejected_write_tag_step_has_no_second_claimer():
    m = handoff_w(to="any")
    rej = claim(5, "B2", 1, "failed", 2, reason="rejected")
    rej.metadata["event_payload"]["access"] = "write"
    msgs = [plan_msg(plan=TAG), start_msg(), claim(3, "B1", 0, "done"), m, rej]
    ev = BotMessage("C", m.ts, TOP, "B1", m.metadata["event_payload"], "UA")
    assert act(ev, state(msgs, me="B1")) == ("ignore", "rejected")
    # also after a restart: the catch-up pass offers no claim
    assert wake_all(Wake(TOP, 9e9), state(msgs, me="B1")) == []
