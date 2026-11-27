from types import SimpleNamespace as NS

from pipe.core.gate import gate_decision, gate_required, gate_text, in_allowlist, step_rejected

W, R = NS(access="write"), NS(access="read")


def test_in_allowlist_exact():
    assert in_allowlist(["B1", "U1"], "B1")
    for s in (None, "", "b1", "B1 "):
        assert not in_allowlist(["B1"], s)
    assert not in_allowlist([], "B1")


def test_gate_required_only_write_from_other_person():
    assert gate_required(W, "U2", "U1")
    assert not gate_required(R, "U2", "U1")
    assert not gate_required(W, "U1", "U1")
    assert gate_required(W, "U1", "")  # empty owner never matches (fail closed)
    assert gate_required(W, None, "U1")


def test_gate_required_when_a_non_owner_human_spoke():
    assert not gate_required(W, "U1", "U1", ["U1", "U1"])
    assert gate_required(W, "U1", "U1", ["U1", "U2"])
    assert gate_required(R, "U1", "U1", ["U2"]) is False


def test_gate_decision_table():
    al = ["B1", "U3"]
    assert gate_decision("B1", "U9", "U9", al) == "auto"  # starter is sender owner
    assert gate_decision("B1", "U3", "U9", al) == "auto"  # starter allowlisted
    assert gate_decision("B1", "B1", "U9", al) == "auto"  # trigger bot allowlisted
    assert gate_decision("B1", "U7", "U9", al) == "button"  # stranger
    assert gate_decision("B1", None, "U9", al) == "button"  # unknown starter
    assert gate_decision("B2", "U3", "U9", al) == "button"  # sender not allowlisted
    assert gate_decision("B1", "", "", al) == "button"  # empty never matches
    assert gate_decision("B1", "U9", "U9", []) == "button"


def c(step, status, reason=None, ts="1.1", by="A"):
    return NS(step=step, status=status, reason=reason, ts=ts, by=by)


def test_step_rejected():
    rej = c(2, "failed", "rejected", "5.1")
    assert step_rejected([c(2, "claimed", None, "4.1"), rej], 2)
    assert not step_rejected([rej], 1)
    assert not step_rejected([c(2, "failed", "run_failed")], 2)
    assert not step_rejected([rej, c(2, "running", None, "6.1")], 2)  # later claim wins
    assert not step_rejected([], 2)


def test_gate_text():
    assert gate_text(2, 3, "coder-bob", "U_OWNER", "coder-pavlo") == (
        "Step 2 of 3 (write, coder-bob): needs approval. <@U_OWNER> "
        "Accept or reject this work from coder-pavlo."
    )
