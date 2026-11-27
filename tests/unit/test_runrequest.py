from types import SimpleNamespace as NS

import pytest

from pipe.core.runrequest import RunRequest, build_run_request, planner_request


def step(access="read", cap="cap-1", **kw):
    return NS(access=access, capability=cap, payload=kw.get("payload"), target=kw.get("target"))


def test_owner_started():
    assert build_run_request(step(), "U1", "U1") == RunRequest(("cap-1",), "read", True)


def test_other_starter_and_empty_owner_fail_closed():
    assert not build_run_request(step(), "U2", "U1").requester_is_owner
    assert not build_run_request(step(), "U1", None).requester_is_owner
    assert not build_run_request(step(), None, None).requester_is_owner
    assert not build_run_request(step(), "", "").requester_is_owner


def test_only_own_capability():
    assert build_run_request(step(cap="x"), "U", "U").capabilities == ("x",)


def test_approve_raises():
    with pytest.raises(ValueError):
        build_run_request(step("approve"), "U", "U")


def test_write_keeps_access():
    req = build_run_request(step("write"), "U", "U")
    assert req.access == "write" and req.capabilities == ("cap-1",)


def test_planner_request():
    assert planner_request() == RunRequest((), "read", False)


def test_exposure_check():
    assert build_run_request(step(), "U", "U", exposed={"cap-1"}).capabilities == ("cap-1",)
    with pytest.raises(ValueError):
        build_run_request(step(), "U", "U", exposed={"other"})  # owner-only never loads


def test_payload_and_schema_carried():
    r = build_run_request(step(payload={"a": 1}), "U", "U", output_schema={"type": "object"})
    assert r.payload == {"a": 1}
    assert r.output_schema == {"type": "object"}
    assert r.target is None


def test_no_tool_fields():
    assert set(RunRequest.__dataclass_fields__) == {
        "capabilities",
        "access",
        "requester_is_owner",
        "target",
        "payload",
        "output_schema",
    }


def test_no_step_tools():
    import pipe.core.runrequest as m

    assert not hasattr(m, "step_tools")
