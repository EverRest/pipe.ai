import io
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import urllib.request  # noqa: E402

import pytest  # noqa: E402

from fakes import FakeCallSlack  # noqa: E402
from pipe import hook, state  # noqa: E402
from pipe import transport_slack_http as http  # noqa: E402

SID = "sess-1"


@pytest.fixture(autouse=True)
def cfg(pipe_home):
    (pipe_home / "config.yaml").write_text(
        "agent_name: coder\nslack_tokens: keychain:pipe-x\nowner: U1\n"
    )


def run(event, fake, sid=SID, cwd=None, **kw):
    data = json.dumps({"session_id": sid, "cwd": str(cwd or "/nonexistent/myrepo")})
    return hook.run(event, io.StringIO(data), call_slack=fake, **kw)


def test_one_post_then_updates():
    f = FakeCallSlack()
    for ev in ("SessionStart", "Stop", "SessionEnd"):
        assert run(ev, f) == 0
    assert [m for m, _ in f.calls] == ["chat.postMessage", "chat.update", "chat.update"]
    assert f.calls[1][1]["ts"] == "1700000001.000000"
    stages = [p["metadata"]["event_payload"]["stage"] for _, p in f.calls]
    assert stages == ["started", "idle", "stopped"]
    ep = f.calls[0][1]["metadata"]
    assert ep["event_type"] == "pipe.status.v1"
    assert isinstance(ep["event_payload"]["updated_at"], int)
    assert f.calls[0][1]["channel"] == "#pipe-status"
    assert state.load_state()["status_channel_id"] == "C_STATUS"
    assert state.load_session(SID)["ts"] == "1700000001.000000"


def test_channel_id_used_after_cache():
    f = FakeCallSlack()
    run("Stop", f)
    run("Stop", f, sid="other")
    assert f.calls[1][1]["channel"] == "C_STATUS"


def test_stop_without_state_posts():
    f = FakeCallSlack()
    run("SessionEnd", f)
    assert f.calls[0][0] == "chat.postMessage"
    assert f.calls[0][1]["metadata"]["event_payload"]["stage"] == "stopped"


def test_text_and_repo_escaped(tmp_path):
    d = tmp_path / "<!channel>"
    d.mkdir()
    f = FakeCallSlack()
    run("Stop", f, cwd=d)
    p = f.calls[0][1]
    assert "<!channel>" not in p["text"]
    assert p["metadata"]["event_payload"]["repo"] == "&lt;!channel&gt;"
    assert p["metadata"]["event_payload"]["branch"] == ""
    assert p["text"].endswith("| idle | blocker: none")


def test_errors_exit_0_and_log(pipe_home):
    assert run("Stop", FakeCallSlack(error=TimeoutError())) == 0
    assert "TimeoutError" in (pipe_home / "logs" / "hook.log").read_text()
    assert run("Stop", FakeCallSlack(response={"ok": False, "error": "bad"}), sid="b") == 0


@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"session_id": "../x"}', '{"cwd": "/"}'])
def test_bad_input_exit_0(stdin):
    f = FakeCallSlack()
    assert hook.run("Stop", io.StringIO(stdin), call_slack=f) == 0
    assert f.calls == []


def test_missing_config_exit_0(pipe_home):
    (pipe_home / "config.yaml").unlink()
    assert run("Stop", FakeCallSlack()) == 0


def test_guard(monkeypatch, pipe_home):
    monkeypatch.setenv("PIPE_RUNTIME", "1")
    f = FakeCallSlack()
    assert run("Stop", f) == 0
    assert f.calls == [] and not (pipe_home / "status").exists()
    monkeypatch.setenv("PIPE_RUNTIME", "")
    run("Stop", f)
    assert len(f.calls) == 1


def test_stale_lock_removed_fresh_kept(pipe_home):
    lock = pipe_home / "status" / f"{SID}.lock"
    lock.parent.mkdir()
    lock.write_text("")
    old = time.time() - 60
    os.utime(lock, (old, old))
    f = FakeCallSlack()
    run("Stop", f)
    assert f.calls[0][0] == "chat.postMessage" and not lock.exists()


def test_fresh_lock_waits_then_updates(pipe_home, monkeypatch):
    lock = pipe_home / "status" / f"{SID}.lock"
    lock.parent.mkdir()
    lock.write_text("")
    f = FakeCallSlack()
    # the other process finishes its post while we wait
    monkeypatch.setattr(
        hook.time,
        "sleep",
        lambda s: state.save_session(SID, {"channel": "C", "ts": "9.9", "started_at": "x"}),
    )
    run("Stop", f)
    assert f.calls[0][0] == "chat.update" and f.calls[0][1]["ts"] == "9.9"
    assert lock.exists()  # not ours


def test_default_call_slack_timeout(monkeypatch):
    seen = {}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake(req, timeout=None):
        seen["timeout"] = timeout
        seen["auth"] = req.get_header("Authorization")
        return R(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert http.call_slack("chat.update", {"a": 1}, token="t")  # noqa: S106 == {"ok": True}
    assert seen["timeout"] == 5 and seen["auth"] == "Bearer t"


def test_no_slack_sdk_imports():
    src = Path(hook.__file__).read_text() + Path(http.__file__).read_text()
    assert not re.search(r"^\s*(import|from) slack_(bolt|sdk)", src, re.M)


def test_branch_token_scrubbed(monkeypatch):
    monkeypatch.setattr(
        hook, "_git", lambda cwd, *a: "xoxb-123456789-abcdefgh" if "--abbrev-ref" in a else ""
    )
    f = FakeCallSlack()
    run("Stop", f)
    p = f.calls[0][1]
    assert "xoxb-" not in p["text"] and "[redacted]" in p["text"]
    assert "xoxb-" not in p["metadata"]["event_payload"]["branch"]
