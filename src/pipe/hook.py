"""Status hook: one Slack message per Claude Code session. Never exits non-zero."""

import contextlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from pipe import state
from pipe.config import load_config
from pipe.keychain import read_token
from pipe.transport_slack_http import call_slack as http_call
from pipe.transport_slack_map import escape_mentions

STAGES = {"SessionStart": "started", "Stop": "idle", "SessionEnd": "stopped"}
LOCK_STALE_S = 30
WAIT_S = 5


def _log() -> None:
    p = state.pipe_home() / "logs" / "hook.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {traceback.format_exc()}\n")


def _git(cwd: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    return r.stdout.strip() if r.returncode == 0 else ""


def _lock(path: Path) -> bool:
    """Take the first-post lock. Remove a stale one first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if time.time() - path.stat().st_mtime > LOCK_STALE_S:
            path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    except FileExistsError:
        return False
    return True


def _wait_for_session(sid: str) -> dict | None:
    end = time.time() + WAIT_S
    while time.time() < end:
        if (s := state.load_session(sid)) and s.get("ts"):
            return s
        time.sleep(0.1)
    return None


def _run(event: str, data: dict, call_slack) -> None:
    sid = data["session_id"]
    cwd = data.get("cwd") or ""
    cfg = load_config()
    if call_slack is None:
        token = read_token(cfg.slack_tokens.removeprefix("keychain:"), "bot")
        call_slack = lambda m, p: http_call(m, p, token)  # noqa: E731
    stage = STAGES[event]
    prior = state.load_session(sid)
    lock = state.pipe_home() / "status" / f"{sid}.lock"
    held = False
    if not (prior and prior.get("ts")):
        held = _lock(lock)
        prior = state.load_session(sid) if held else _wait_for_session(sid)
        if prior and prior.get("ts") and held:  # filled in while we took the lock
            lock.unlink(missing_ok=True)
            held = False
    try:
        now = int(time.time())
        started = (prior or {}).get("started_at") or time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)
        )
        repo = _git(cwd, "rev-parse", "--show-toplevel") or cwd
        repo = escape_mentions(Path(repo).name)
        branch = escape_mentions(_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")) if cwd else ""
        who = escape_mentions(cfg.agent_name)
        payload = {
            "v": 1,
            "session_id": sid,
            "who": who,
            "repo": repo,
            "branch": branch,
            "stage": stage,
            "blocker": "",
            "started_at": started,
            "updated_at": now,
        }
        body = {
            "text": f"{who} | {repo} | {branch} | {stage} | blocker: none",
            "metadata": {"event_type": "pipe.status.v1", "event_payload": payload},
        }
        if prior and prior.get("ts"):
            method = "chat.update"
            body |= {"channel": prior["channel"], "ts": prior["ts"]}
        else:
            method = "chat.postMessage"
            body["channel"] = (
                state.load_state().get("status_channel_id") or f"#{cfg.status_channel}"
            )
        r = call_slack(method, body)
        if not r.get("ok"):
            raise RuntimeError(f"slack {method}: {r.get('error')}")
        if method == "chat.postMessage":
            state.save_state(status_channel_id=r["channel"])
            state.save_session(sid, {**payload, "channel": r["channel"], "ts": r["ts"]})
        else:
            state.save_session(sid, {**prior, **payload})
    finally:
        if held:
            lock.unlink(missing_ok=True)


def run(event: str, stdin, call_slack=None) -> int:
    """Handle one hook event. Always returns 0."""
    if os.environ.get("PIPE_RUNTIME"):
        return 0
    try:
        data = json.load(stdin)
        if not isinstance(data, dict):
            raise ValueError("hook input is not an object")
        state.load_session(str(data.get("session_id", "")))  # validates the id
        _run(event, data, call_slack)
    except Exception:
        with contextlib.suppress(Exception):
            _log()
    return 0


def main(event: str) -> int:
    return run(event, sys.stdin)
