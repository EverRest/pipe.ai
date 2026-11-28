"""templates/e2e wrapper. A fake runner only: no Playwright, npm, or network."""

import importlib.util
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from pipe.config import validate_config
from pipe.core.contract import RuntimeFailed, RuntimeInput
from pipe.core.runrequest import RunRequest
from pipe.core.schema import validate_schema
from pipe.runtime_exec import ExecRuntime

P = Path(__file__).resolve().parents[2] / "templates/e2e/e2e_capability.py"
spec = importlib.util.spec_from_file_location("e2e_cap", P)
e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e2e)


class Runner:
    """Fake Playwright: writes the log and, if asked, one screenshot."""

    def __init__(self, rc=0, log="2 passed", shot=False):
        self.rc, self.log, self.shot, self.calls = rc, log, shot, []

    def __call__(self, argv, env, cwd, timeout, log_path):
        self.calls.append(SimpleNamespace(argv=argv, env=env, cwd=cwd, timeout=timeout))
        Path(log_path).write_text(self.log)
        if self.shot:
            out = Path(next(a for a in argv if a.startswith("--output=")).split("=", 1)[1])
            (out / "t1").mkdir(parents=True)
            (out / "t1" / "test-failed-1.png").write_bytes(b"png")
            (out / "t1" / "link.png").symlink_to("/etc/hosts")
        return self.rc


@pytest.fixture
def cfg(tmp_path):
    cli = tmp_path / "co/node_modules/@playwright/test/cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("")
    return {
        "checkout": str(tmp_path / "co"),
        "node": "/opt/node/bin/node",
        "envs": {"staging": "https://staging.example.com", "qa": "https://qa.example.com"},
        "default_env": "staging",
    }


@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    return d


def go(cfg, run_dir, payload=None, runner=None, environ=None):
    r = runner or Runner()
    inp = {"goal": "Run the tests", "task": {}}
    if payload is not None:
        inp["payload"] = payload
    rc, out = e2e.run(inp, cfg, run_dir, r, environ or {"HOME": "/h"})
    return rc, out, r


def test_default_env_argv_and_minimal_child_env(cfg, run_dir):
    environ = {"HOME": "/h", "PATH": "/evil", "SLACK_TOKEN": "x", "PIPE_RUNTIME": "1"}
    rc, out, r = go(cfg, run_dir, environ=environ)
    assert (rc, out["status"]) == (0, "done")
    c = r.calls[0]
    assert c.argv == [
        "/opt/node/bin/node",
        f"{cfg['checkout']}/node_modules/@playwright/test/cli.js",
        "test",
        "--reporter=line",
        f"--output={run_dir}/test-results",
    ]
    assert c.env == {
        "HOME": "/h",
        "PATH": "/opt/node/bin:/usr/bin:/bin",
        "BASE_URL": "https://staging.example.com",
        "CI": "1",
    }
    assert c.cwd == cfg["checkout"] and c.timeout == 540
    assert out["files"] == ["report.txt"]
    report = (run_dir / "report.txt").read_text()
    assert "Environment: staging" in report and "2 passed" in report


def test_env_name_picks_url_and_filter_is_last_argument(cfg, run_dir):
    _, _, r = go(cfg, run_dir, {"env": "qa", "filter": "login/smoke.spec.ts"})
    assert r.calls[0].env["BASE_URL"] == "https://qa.example.com"
    assert r.calls[0].argv[-1] == "login/smoke.spec.ts"


@pytest.mark.parametrize(
    "payload",
    [
        {"env": "prod"},
        {"env": "https://evil.example.com"},
        {"env": 1},
        {"filter": "--config=/tmp/x"},
        {"filter": "-x"},
        {"filter": "/etc/passwd"},
        {"filter": "a/../../b"},
        {"filter": "a b"},
        {"filter": "a\n"},
        {"filter": ""},
        {"filter": "a" * 101},
        {"filter": ["a"]},
    ],
)
def test_bad_input_runs_nothing(cfg, run_dir, payload):
    rc, out, r = go(cfg, run_dir, payload)
    assert rc == 2 and "status" not in out and not r.calls


def test_url_or_args_in_input_are_ignored(cfg, run_dir):
    _, _, r = go(cfg, run_dir, {"url": "https://evil.example.com", "args": ["-x"]})
    assert r.calls[0].env["BASE_URL"] == "https://staging.example.com"
    assert "-x" not in r.calls[0].argv


def test_test_failure_is_failed_status_with_exit_0_and_files(cfg, run_dir):
    rc, out, _ = go(cfg, run_dir, runner=Runner(rc=1, log="1 failed", shot=True))
    assert rc == 0 and out["status"] == "failed"
    assert out["files"] == ["report.txt", "test-results/t1/test-failed-1.png"]


@pytest.mark.parametrize("code", [2, 127, -9])
def test_runner_breakdown_is_not_a_test_failure(cfg, run_dir, code):
    rc, out, _ = go(cfg, run_dir, runner=Runner(rc=code))
    assert rc == 1 and "status" not in out


def test_timeout_and_missing_program(cfg, run_dir):
    for exc in (subprocess.TimeoutExpired("x", 1), FileNotFoundError()):

        def boom(*a, exc=exc):
            raise exc

        rc, out, _ = go(cfg, run_dir, runner=boom)
        assert rc == 1 and "status" not in out


def test_secrets_are_redacted_in_text_and_report(cfg, run_dir):
    log = (
        "\x1b[31mAuthorization: Bearer abc123def\x1b[0m password=hunter2 "
        'glpat-abcdefghij "token": "tok-999" https://bob:pw9@x.example.com'
    )
    _, out, _ = go(cfg, run_dir, runner=Runner(log=log))
    seen = out["text"] + (run_dir / "report.txt").read_text()
    for s in ("abc123def", "hunter2", "glpat-abcdefghij", "tok-999", "pw9", "\x1b"):
        assert s not in seen
    assert not (run_dir / "playwright.log").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"envs": {}},
        {"envs": {"staging": "http://staging.example.com"}},
        {"envs": {"staging": "https://u:p@staging.example.com"}},
        {"envs": {"staging": "file:///etc/passwd"}},
        {"default_env": "nope"},
        {"checkout": "relative/dir"},
        {"node": "node"},
        {"timeout_s": 0},
    ],
)
def test_bad_owner_file_runs_nothing(cfg, run_dir, change):
    rc, _, r = go({**cfg, **change}, run_dir)
    assert rc == 2 and not r.calls


def test_playwright_not_installed(cfg, run_dir, tmp_path):
    rc, out, r = go({**cfg, "checkout": str(tmp_path)}, run_dir)
    assert rc == 2 and not r.calls and "not installed" in out["text"]


def test_main_reads_owner_file_and_stdin(cfg, run_dir, tmp_path, monkeypatch, capsys):
    f = tmp_path / "e2e.json"
    f.write_text(json.dumps(cfg))
    monkeypatch.chdir(run_dir)
    monkeypatch.setattr("sys.stdin", io.StringIO('{"goal": "g", "payload": {"env": "qa"}}'))
    r = Runner()
    assert e2e.main([str(f)], r) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "done"
    assert r.calls[0].env["BASE_URL"] == "https://qa.example.com"
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert e2e.main([str(tmp_path / "missing.json")], r) == 2


def example():
    ex = yaml.safe_load((P.parent / "config.example.yaml").read_text())
    return validate_config({"agent_name": "a", "slack_tokens": "keychain:x", **ex})


def test_example_config_loads_and_accepts_the_pipeline_payload():
    c = example()
    cap = c.capabilities[0]
    assert cap["access"] == "read" and c.exposed == ["exec:e2e"]
    assert c.tags["exec:e2e"] == ["e2e"]
    schema = cap["input_schema"]
    ctx = [{"step": 0, "text": "t", "artifacts": []}]
    assert not validate_schema({"context": ctx, "artifacts": []}, schema)
    assert not validate_schema({}, schema)
    assert validate_schema({"url": "x"}, schema)
    owner_file = json.loads((P.parent / "e2e.example.json").read_text())
    assert cap["timeout_s"] > owner_file["timeout_s"]
    assert cap["env_allow"] == ["HOME"]


@pytest.mark.parametrize(("code", "status"), [(0, "done"), (1, "failed")])
def test_output_passes_the_real_exec_runtime(cfg, tmp_path, monkeypatch, code, status):
    c = example()
    fake = Runner(rc=code, shot=True)

    def exec_runner(argv, stdin, env, cwd, timeout):
        rc, out = e2e.run(json.loads(stdin), cfg, Path(cwd), fake, env)
        return rc, json.dumps(out), ""

    rt = ExecRuntime(c, runner=exec_runner, home=tmp_path / "home")
    req = RunRequest(("exec:e2e",), "read", False)
    task = {"id": "1.0", "step": 0, "pipeline": {"goal": "g"}, "payload": {"env": "qa"}}
    o = rt.run(RuntimeInput([], task, False, req))
    assert o.status == status
    assert [Path(f).name for f in o.files] == ["report.txt", "test-failed-1.png"]
    assert fake.calls[0].env["BASE_URL"] == "https://qa.example.com"
    task["payload"] = {"env": "prod"}
    with pytest.raises(RuntimeFailed, match="exit 2"):
        rt.run(RuntimeInput([], task, False, req))
