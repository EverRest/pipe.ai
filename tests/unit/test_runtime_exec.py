import contextlib
import json
import logging
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from pipe.core.contract import RuntimeFailed, RuntimeInput
from pipe.runtime_exec import ExecRuntime

OK = json.dumps({"text": "hi", "status": "done"})
ENTRY = {
    "id": "t", "runtime": "exec", "name": "T", "description": "d", "access": "read",
    "command": ["/bin/tool", "; rm -rf /", "$(id)"], "env_allow": ["FOO"], "timeout_s": 5,
}  # fmt: skip


def cfg(exposed=("exec:t",), entry=ENTRY):
    return NS(capabilities=[entry], exposed=list(exposed), step_timeout_min=30)


def inp(caps=("exec:t",), access="read", owner=True, schema=None, payload=None):
    task = {"id": "T1", "purpose": "step", "step": 1, "pipeline": {"goal": "g"}}
    if payload is not None:
        task["payload"] = payload
    req = NS(capabilities=caps, access=access, requester_is_owner=owner, output_schema=schema)
    return RuntimeInput(
        thread=[{"user": "u", "text": "secret thread"}],
        task=task,
        requester_is_owner=owner,
        request=req,
    )


class Runner:
    def __init__(self, rc=0, out=OK, err="", exc=None):
        self.rc, self.out, self.err, self.exc, self.calls = rc, out, err, exc, []

    def __call__(self, argv, stdin, env, cwd, timeout):
        self.calls.append(NS(argv=argv, stdin=stdin, env=env, cwd=cwd, timeout=timeout))
        if self.exc:
            raise self.exc
        return self.rc, self.out, self.err


def rt(r, home, c=None, **kw):
    return ExecRuntime(c or cfg(), runner=r, home=home, **kw)


def test_run_ok_argv_stdin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    monkeypatch.setenv("SLACK_TOKEN", "xoxb-leak")
    r = Runner()
    out = rt(r, tmp_path).run(inp(schema={"type": "object"}, payload={"a": 1}))
    c = r.calls[0]
    assert out.text == "hi" and out.status == "done"
    assert c.argv == ENTRY["command"] and c.timeout == 5
    assert c.env == {"FOO": "bar", "PIPE_RUNTIME": "1"}
    assert json.loads(c.stdin) == {
        "goal": "g", "payload": {"a": 1}, "task": {"id": "T1", "step": 1},
        "output_schema": {"type": "object"},
    }  # fmt: skip
    assert "secret thread" not in c.stdin


def test_no_env_allow_and_no_optional_input(tmp_path):
    e = {k: v for k, v in ENTRY.items() if k != "env_allow"}
    r = Runner()
    rt(r, tmp_path, cfg(entry=e)).run(inp())
    assert r.calls[0].env == {"PIPE_RUNTIME": "1"}
    assert set(json.loads(r.calls[0].stdin)) == {"goal", "task"}


def test_cwd_removed_after_ok_fail_timeout(tmp_path):
    seen = []

    def run(argv, stdin, env, cwd, timeout):
        assert Path(cwd).is_dir() and not list(Path(cwd).iterdir())
        seen.append(cwd)
        if len(seen) == 2:
            raise subprocess.TimeoutExpired(argv, timeout)
        return (0, OK, "") if len(seen) == 1 else (1, "", "")

    for _ in range(3):
        with contextlib.suppress(RuntimeFailed):
            rt(run, tmp_path).run(inp())
    assert len(seen) == 3 and not any(Path(s).exists() for s in seen)


@pytest.mark.parametrize(
    "out", ["nope", json.dumps({"status": "done"}), json.dumps({"text": "x", "status": "bad"})]
)
def test_bad_output(tmp_path, out):
    with pytest.raises(RuntimeFailed):
        rt(Runner(out=out), tmp_path).run(inp())


def test_too_large(tmp_path):
    big = json.dumps({"text": "x" * 1_100_000, "status": "done"})
    with pytest.raises(RuntimeFailed, match="result too large"):
        rt(Runner(out=big), tmp_path).run(inp())


def test_exit_and_timeout(tmp_path):
    with pytest.raises(RuntimeFailed) as e:
        rt(Runner(rc=3), tmp_path).run(inp())
    assert str(e.value) == "exit 3"
    with pytest.raises(RuntimeFailed) as e:
        rt(Runner(exc=subprocess.TimeoutExpired(["x"], 1)), tmp_path).run(inp())
    assert str(e.value) == "timeout"


def test_default_timeout_from_step_minutes(tmp_path):
    e = {k: v for k, v in ENTRY.items() if k != "timeout_s"}
    r = Runner()
    rt(r, tmp_path, cfg(entry=e)).run(inp())
    assert r.calls[0].timeout == 30 * 60


def test_scrub_escape_artifacts(tmp_path):
    out = json.dumps(
        {
            "text": "tok xoxb-abcdefghij <!here>",
            "status": "done",
            "artifacts": ["https://a.example/x", "file:///etc/passwd", "http://b.example"],
        }
    )
    o = rt(Runner(out=out), tmp_path, escape_mentions=lambda s: s.replace("<!", "<\\!")).run(inp())
    assert o.text == "tok [redacted] <\\!here>"
    assert o.artifacts == ["https://a.example/x"]


@pytest.mark.parametrize("owner", [True, False])
@pytest.mark.parametrize(
    "c,caps",
    [(cfg(exposed=()), ("exec:t",)), (cfg(), ("exec:zzz",)), (cfg(), ()), (cfg(), ("exec:t", "x"))],
)
def test_refused(tmp_path, owner, c, caps):
    r = Runner()
    with pytest.raises(RuntimeFailed, match="capability not available"):
        rt(r, tmp_path, c).run(inp(caps=caps, owner=owner))
    assert r.calls == []


def test_refuses_write_and_no_request(tmp_path):
    r = Runner()
    with pytest.raises(RuntimeFailed):
        rt(r, tmp_path).run(inp(access="write"))
    bare = RuntimeInput(thread=[], task={}, requester_is_owner=True)
    with pytest.raises(RuntimeFailed):
        rt(r, tmp_path).run(bare)
    assert r.calls == []


def test_no_secret_in_log_or_error(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    r = Runner(rc=1, err="boom xoxb-abcdefghij " + "y" * 300)
    with pytest.raises(RuntimeFailed) as e:
        rt(r, tmp_path).run(inp())
    text = caplog.text + str(e.value)
    assert "xoxb-abcdefghij" not in text and "rm -rf" not in text and "$(id)" not in text
    assert "boom" in caplog.text and "y" * 201 not in caplog.text
