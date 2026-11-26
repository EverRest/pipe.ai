import json

import pytest

from pipe.core.contract import RuntimeFailed, RuntimeOutput, parse_output


def out(**kw):
    return json.dumps({"text": "hi", "status": "done", **kw})


def test_valid_full():
    r = parse_output(out(next={"agent": "a", "access": "x", "payload": {}}, artifacts=["l1"]))
    assert isinstance(r, RuntimeOutput)
    assert (r.text, r.status, r.artifacts) == ("hi", "done", ["l1"])
    assert r.next["agent"] == "a"
    assert r.data is None and r.reason is None and r.proposal is None


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps({"status": "done"}),
        json.dumps({"text": "x", "status": "bogus"}),
        json.dumps(["x"]),
    ],
)
def test_invalid_raises(raw):
    with pytest.raises(RuntimeFailed):
        parse_output(raw)


@pytest.mark.parametrize("s", ["done", "needs_approval", "waiting", "failed", "delegate"])
def test_statuses(s):
    assert parse_output(out(status=s)).status == s


def test_data_object_kept_and_non_object_rejected():
    assert parse_output(out(data={"a": 1})).data == {"a": 1}
    with pytest.raises(RuntimeFailed):
        parse_output(out(data=[1]))


def test_waiting_with_reason():
    r = parse_output(out(status="waiting", reason="needs_input", text="Which repo?"))
    assert (r.status, r.reason, r.text) == ("waiting", "needs_input", "Which repo?")


def test_reason_dropped_on_other_status_and_capped():
    assert parse_output(out(reason="x")).reason is None
    assert len(parse_output(out(status="failed", reason="y" * 300)).reason) == 200
    with pytest.raises(RuntimeFailed):
        parse_output(out(status="failed", reason=5))


def test_proposal():
    assert parse_output(out(proposal={"steps": []})).proposal == {"steps": []}
    with pytest.raises(RuntimeFailed):
        parse_output(out(proposal=["x"]))
    with pytest.raises(RuntimeFailed):
        parse_output(out(proposal={"k": "z" * 4001}))
