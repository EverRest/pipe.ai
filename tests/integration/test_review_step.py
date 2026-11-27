"""A review step is a normal step on a `review`-tagged capability (no review code in the core)."""

import pytest

from pipe.core.capability import Capability
from pipe.core.pipeline import validate_plan
from pipe.core.route import BotMessage, card_view, route
from thread_kit import CARDS, TOP, claim, plan_msg, start_msg, state, step, task
from unit.test_stepper import Rig, meta

MR = "https://x/mr/1"
# the schema subset has no anyOf: `artifacts` stands for "a change link" here
SCHEMA = {
    "type": "object",
    "required": ["artifacts"],
    "properties": {"mr_url": {"type": "string"}, "artifacts": {"type": "array"}, "context": {}},
    "additionalProperties": False,
}
REVIEW = {**step("any", "tag:review"), "exclude_agents_of": [0]}
PLAN_A = {"steps": [step("B1", "cap-1", access="write"), REVIEW], "source": "free"}
PLAN_B = {"steps": [step("B1", "cap-1", access="write"), step("B2", "cap-2")], "source": "free"}
CAP = {"cap-2": Capability("cap-2", "wr", tags=("review",), input_schema=SCHEMA)}


def seed(arts=(MR,), to="any"):
    extra = {} if arts is None else {"artifacts": list(arts)}
    nxt = {"agent": to, "access": "read", "payload": {"step": 1}}
    h = task(
        4,
        "B1",
        "step",
        "done",
        2,
        step=0,
        access="write",
        next=nxt,
        text="made MR\nStep 2 of 2",
        **extra,
    )
    return [start_msg(2), claim(3, "B1", 0, "done"), h]


def rig(plan=PLAN_A, arts=(MR,), to="any"):
    msgs = seed(arts, to)
    r = Rig("B2", plan=plan, seed=msgs, caps=CAP)
    return r, r.ev(msgs[-1])


@pytest.mark.parametrize(("plan", "to"), [(PLAN_A, "any"), (PLAN_B, "B2")])
def test_review_gets_the_link_and_context_in_the_payload(plan, to):
    r, ev = rig(plan, to=to)
    assert r.st.run_step(ev, 1) == "done"
    inp = r.rt.inputs[0]
    assert inp.request.capabilities == ("cap-2",) and inp.request.access == "read"
    assert inp.task["payload"]["artifacts"] == [MR]
    assert inp.task["payload"]["context"][0]["text"] == "made MR"


def test_no_link_fails_invalid_payload_with_retry_and_no_run():
    r, ev = rig(arts=None)
    r.st.run_step(ev, 1)
    assert not r.rt.inputs
    u = r.ft.updates[-1]
    assert meta(u)["reason"] == "invalid_payload" and u["buttons"]


def test_coder_is_excluded_and_the_reviewer_claims():
    # B1 also has the tag `review` (thread_kit card); `exclude_agents_of` keeps it out
    msgs = [plan_msg(plan=PLAN_A), *seed()]
    ev = BotMessage("C", msgs[-1].ts, TOP, "B1", meta(msgs[-1]), msgs[-1].sender_handle)
    assert route(ev, state(msgs, me="B1")).reason == "excluded"
    assert route(ev, state(msgs, me="B2")).action == "claim"


def test_plan_needs_an_agent_with_the_tag():
    cards = {k: {**c, "skills": [{"id": "x"}]} for k, c in CARDS.items()}
    errs = validate_plan(PLAN_A, card_view(cards), "U9")
    assert any("no agent offers tag review" in e for e in errs)
    assert validate_plan(PLAN_A, card_view(CARDS), "U9") == []
