from types import SimpleNamespace as NS

from pipe.core.contract import RuntimeOutput
from pipe.runtime_select import check_input, check_output, pick_runtime

SCHEMA = {"type": "object", "required": ["n"], "properties": {"n": {"type": "integer"}}}


def test_pick_runtime():
    assert pick_runtime(NS(runtime="exec")) == "exec"
    assert pick_runtime(NS(runtime="http")) == "http"
    assert pick_runtime(NS(runtime="claude")) == "claude"


def test_check_input():
    assert check_input({"n": 1}, None) is None
    assert check_input("anything", None) is None
    assert check_input({"n": 1}, SCHEMA) is None
    reason, errs = check_input({"n": "secret-value"}, SCHEMA)
    assert reason == "invalid_payload" and errs == ["payload.n: expected integer"]
    assert "secret-value" not in str(errs)
    assert check_input(None, SCHEMA)[0] == "invalid_payload"  # missing counts as {}
    assert check_input(None, {"type": "object"}) is None


def test_check_output():
    ok = RuntimeOutput("t", data={"n": 1})
    assert check_output(ok, None) is None
    assert check_output(RuntimeOutput("t"), None) is None
    assert check_output(ok, SCHEMA) is None
    reason, errs = check_output(RuntimeOutput("t", data={"n": "x"}), SCHEMA)
    assert reason == "invalid_result" and errs == ["data.n: expected integer"]
    assert check_output(RuntimeOutput("t"), SCHEMA)[0] == "invalid_result"  # no data
    assert check_output(RuntimeOutput("t"), {})[0] == "invalid_result"


def test_inputs_not_changed():
    p = {"n": 1}
    check_input(p, SCHEMA)
    assert p == {"n": 1}
