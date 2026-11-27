import copy
from types import SimpleNamespace as NS

from pipe.core.pipeline import Pipeline, Step, access_fits, matches_tag, validate_plan

H = "a" * 32


def card(owner, *skills):
    return NS(owner=owner, skills=[dict(s) for s in skills])


CARDS = {
    "B1": card("O1", {"id": "cap-1", "tags": ["review"]}, {"id": "cap-w", "access": "write"}),
    "B2": card("O2", {"id": "cap-2", "tags": ["x"], "access": "read"}),
    "B3": card("O3", {"id": "cap-3"}),
}


def bot(agent="B1", cap="cap-1", **kw):
    return {"agent": agent, "capability": cap, "access": "read", "goal": "do it", **kw}


def human(user="U1"):
    return {"agent": f"human:{user}", "access": "approve", "goal": "ok?"}


def tag(t="review", **kw):
    return bot("any", f"tag:{t}", **kw)


def v(steps, starter=None, flows=None, **kw):
    return validate_plan({"steps": steps, **kw}, CARDS, starter, flows)


def has(errs, text):
    assert any(text in e for e in errs), errs


class Flow:
    def __init__(self, ok=True):
        self.hash, self.ok = H, ok

    def matches(self, steps, cards, starter):
        return self.ok


def test_valid():
    assert v([bot(), bot("B2", "cap-2"), bot("B3", "cap-3"), human("U1")], starter="U1") == []
    assert v([bot(payload={"a": 1}, target="r")]) == []


def test_steps_and_limit():
    has(v([]), "no steps")
    four = [bot(), bot(), bot(), bot()]
    has(v(four), "plan has 4 agent steps, the limit is 3")
    src = {"source": f"template:t@{H}"}
    assert v(four, flows={"t": Flow()}, **src) == []
    has(v([bot()] * 6, flows={"t": Flow()}, **src), "plan has 6 agent steps, the limit is 5")
    assert len(v([bot()] * 5, flows={"t": Flow()}, **src)) == 0
    has(v(four, flows={"t": Flow(False)}, **src), "limit is 3")
    has(v(four, flows={}, **src), "limit is 3")
    has(v(four, **src), "limit is 3")
    has(v(four, source="free"), "limit is 3")
    assert v([bot()], source="free") == []


def test_bad_source():
    for s in ("template:Bad@x", "evil", "template:", 5):
        has(v([bot()], source=s), "bad source")


def test_access():
    assert v([bot("B1", "cap-w", access="write")]) == []
    has(v([{**human(), "access": "write"}]), "step 1")
    has(v([bot(access="zzz")]), "step 1")
    has(v([bot(access="approve")]), "step 1")
    has(v([bot(kind="agent")]), "kind")
    has(v([bot(skill="s")]), "skill")


def test_bot_and_human_shape():
    has(v([{"agent": "B1", "access": "read", "goal": "g"}]), "capability")
    h = human()
    has(v([bot(), {**h, "access": "read"}]), "approve")
    has(v([bot(), {**h, "capability": "cap-1"}]), "capability")
    has(v([bot(), {**h, "payload": {}}]), "payload")
    has(v([bot(), human(), bot()]), "last")
    has(v([bot(), human(), human()]), "last")
    has(v([human(), bot()]), "first step")


def test_cards_and_caps():
    has(v([bot("B9")]), "step 1: agent B9 has no card")
    has(v([bot(), bot("B1", "nope")]), "step 2")
    has(v([bot("B1", "cap-w")]), "step 1")  # card access write does not fit read


def test_goal():
    has(v([bot(goal="")]), "goal")
    has(v([bot(goal="x" * 501)]), "goal")
    assert v([bot(goal="x" * 500)]) == []
    has(v([bot(goal="use xoxb-12345-abcdef")]), "goal")


def test_payload():
    has(v([bot(payload="x")]), "payload")
    has(v([bot(payload={"a": "x" * 2000})]), "payload")


def test_human_approver():
    ok = [bot(), human("U1")]
    assert v(ok, starter="U1") == []
    assert v([bot(), human("O1")], starter="U1") == []  # owner of B1
    has(v([bot(), human("U9")], starter="U1"), "step 2")
    assert v([bot(), human("U9")], starter=None) == []
    has(v([tag(), human("O1")], starter="U1"), "step 2")  # tag step: starter only
    assert v([tag(), human("U1")], starter="U1") == []


def test_tags():
    assert v([tag()]) == []
    has(v([tag("nope")]), "step 1: no agent offers tag nope")
    has(v([bot("any", "cap-1")]), "step 1")
    has(v([bot("B1", "tag:review")]), "step 1")
    for t in ("tag:Review", "tag:", "tag:" + "a" * 33):
        has(v([bot("any", t)]), "step 1")
    has(v([{**tag(), "access": "approve"}]), "step 1")
    has(v([tag(), tag(), tag(), tag()]), "limit is 3")
    assert v([tag(payload={"a": 1})]) == []


def test_helpers():
    assert access_fits("read", None) and access_fits("write", None)
    assert access_fits("read", "read")
    assert not access_fits("read", "write") and not access_fits("write", "read")
    assert matches_tag(CARDS["B1"], "review", "read")
    assert not matches_tag(CARDS["B1"], "zzz", "read")
    assert not matches_tag(
        card("O", {"id": "c", "tags": ["review"], "access": "write"}), "review", "read"
    )
    assert not matches_tag(card("O"), "review", "read")


def test_exclude():
    ok = [bot("B1"), bot("B2", "cap-2", exclude_agents_of=[0])]
    assert v(ok) == []
    has(v([bot(exclude_agents_of=[0])]), "exclude_agents_of")  # not lower
    has(v([bot(), bot("B2", "cap-2", exclude_agents_of=[0, 0])]), "exclude_agents_of")
    has(v([bot(), bot("B2", "cap-2", exclude_agents_of=["0"])]), "exclude_agents_of")
    has(v([bot(), bot("B2", "cap-2", exclude_agents_of=[True])]), "exclude_agents_of")
    has(v([bot(), bot("B2", "cap-2", exclude_agents_of=[0] * 6)]), "exclude_agents_of")
    has(v([bot(), {**human(), "exclude_agents_of": [0]}]), "exclude_agents_of")
    has(v([bot("B1"), bot("B1", exclude_agents_of=[0])]), "step 2: agent B1 holds excluded step 1")
    has(
        v([bot("B1"), tag("review", exclude_agents_of=[0])]),
        "step 2: no agent can claim after exclusion",
    )
    assert v([bot("B1"), tag("x", exclude_agents_of=[0])]) == []  # B2 can claim
    # only B2 offers x, so it holds step 1 for certain (spec 006)
    has(v([tag("x"), tag("x", exclude_agents_of=[0])]), "no agent can claim after exclusion")
    assert v([tag("review"), tag("x", exclude_agents_of=[0])]) == []  # holder unknown
    assert (
        v(
            [
                bot("B1"),
                bot("B2", "cap-2", exclude_agents_of=[0], gate="approval", on_fail=2),
                bot("B3", "cap-3"),
            ]
        )
        == []
    )


def test_gate():
    assert v([bot(gate="approval")]) == []
    has(v([bot(gate="x")]), "gate")
    has(v([bot(), {**human(), "gate": "approval"}]), "gate")


def test_on_fail():
    ok = [bot(on_fail=1), bot("B2", "cap-2")]
    assert v(ok) == []
    has(v([bot(on_fail=1), bot(on_fail=1), bot("B2", "cap-2")]), "on_fail")
    has(v([bot(on_fail=1), bot(), bot()]), "on_fail")  # not the last step
    has(v([bot(), bot(on_fail=1)]), "on_fail")  # last step has it
    has(v([bot(on_fail=1), bot(), human()]), "on_fail")
    has(v([bot(on_fail=0), bot()]), "on_fail")
    has(v([bot(on_fail="1"), bot()]), "on_fail")
    has(v([bot(on_fail=1), bot(on_fail=0)]), "on_fail")


def test_multi_errors_and_pure():
    steps = [bot("B9", goal=""), bot("B8", "z")]
    plan = {"steps": steps}
    before = copy.deepcopy(plan)
    errs = validate_plan(plan, CARDS)
    assert len(errs) >= 3
    assert [e.split(":")[0] for e in errs] == sorted(e.split(":")[0] for e in errs)
    assert plan == before


def test_dataclass_input():
    p = Pipeline(steps=(Step(agent="B1", access="read", goal="g", capability="cap-1"),))
    assert validate_plan(p, CARDS) == []
    bad = Pipeline(steps=(Step(agent="B9", access="read", goal="g", capability="c"),))
    has(validate_plan(bad, CARDS), "no card")


def test_garbage_does_not_raise():
    for plan in (None, 5, {}, {"steps": "x"}, {"steps": [5, None]}, {"steps": [{"agent": 3}]}):
        assert validate_plan(plan, CARDS)


def test_garbage_prev():
    assert validate_plan({"steps": [5, human()]}, CARDS, "U1")
    assert validate_plan({"steps": [{"agent": ["x"]}, human()]}, CARDS, "U1")


def test_trigger_bot_is_never_a_step_agent():
    cards = {**CARDS, "BT": NS(owner="OT", kind="trigger", skills=[])}
    errs = validate_plan({"steps": [bot("B1"), bot("BT", "cap-1")]}, cards)
    assert "step 2: agent BT is a trigger bot" in errs
    assert validate_plan({"steps": [bot("B1"), tag()]}, cards) == []
