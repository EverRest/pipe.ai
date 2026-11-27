"""RuntimePort for a declared `exec` capability (contracts/runtime-exec-http.md)."""

import dataclasses
import json
import logging
import os
import shutil
import signal
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

from pipe.core.contract import RuntimeFailed, RuntimeInput, RuntimeOutput, parse_output
from pipe.core.scrub import scrub as _scrub
from pipe.state import pipe_home

log = logging.getLogger(__name__)
MAX_OUT = 1_000_000
NA = "capability not available"


def find_entry(cfg, inp: RuntimeInput, runtime: str) -> dict:
    """The declared entry of the one requested capability. Refuse if not exposed now."""
    req = inp.request
    ids = tuple(getattr(req, "capabilities", None) or ())
    if len(ids) != 1 or ids[0] not in cfg.exposed:
        raise RuntimeFailed(NA)
    for e in cfg.capabilities:
        if f"{e['runtime']}:{e['id']}" == ids[0] and e["runtime"] == runtime:
            if e.get("access") != "read" or req.access != "read":
                raise RuntimeFailed(NA)
            return e
    raise RuntimeFailed(NA)


def build_input(inp: RuntimeInput) -> str:
    """JSON input. No thread text, no hop, no trust data."""
    t = inp.task
    d = {"goal": (t.get("pipeline") or {}).get("goal", ""), "task": {}}
    d["task"] = {"id": t.get("id"), "step": t.get("step")}
    if t.get("payload") is not None:
        d["payload"] = t["payload"]
    if inp.request.output_schema is not None:
        d["output_schema"] = inp.request.output_schema
    return json.dumps(d)


def finish(raw: str, scrub: Callable, esc: Callable) -> RuntimeOutput:
    """Size limit, parse, scrub, escape. Keep https artifacts only."""
    if len(raw) > MAX_OUT:
        raise RuntimeFailed("result too large")
    o = parse_output(raw)
    arts = [scrub(a) for a in o.artifacts if a.startswith("https://")]
    reason = scrub(o.reason) if o.reason else o.reason
    return dataclasses.replace(o, text=esc(scrub(o.text)), reason=reason, artifacts=arts)


def subprocess_runner(argv, stdin, env, cwd, timeout):
    # ponytail: reads whole output in memory; the size check comes after the run
    p = subprocess.Popen(  # noqa: S603 (argv list, no shell)
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=cwd,
        text=True,
        start_new_session=True,
    )
    try:
        out, err = p.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        raise
    return p.returncode, out, err


class ExecRuntime:
    def __init__(
        self,
        cfg,
        runner=subprocess_runner,
        scrub: Callable = _scrub,
        escape_mentions: Callable = lambda s: s,
        home: Path | None = None,
    ):
        self.cfg, self.runner, self.scrub, self.esc = cfg, runner, scrub, escape_mentions
        self.home = home

    def run(self, inp: RuntimeInput) -> RuntimeOutput:
        e = find_entry(self.cfg, inp, "exec")
        stdin = build_input(inp)
        env = {k: os.environ[k] for k in e.get("env_allow", []) if k in os.environ}
        env["PIPE_RUNTIME"] = "1"
        timeout = e.get("timeout_s", self.cfg.step_timeout_min * 60)
        cwd = (self.home or pipe_home()) / "run" / uuid.uuid4().hex
        cwd.mkdir(parents=True, mode=0o700)
        try:
            try:
                rc, out, err = self.runner(e["command"], stdin, env, str(cwd), timeout)
            except subprocess.TimeoutExpired:
                raise RuntimeFailed("timeout") from None
            if err:
                log.info("exec %s stderr: %s", e["id"], self.scrub(err)[:200])
            if rc != 0:
                raise RuntimeFailed(f"exit {rc}")
            return finish(out, self.scrub, self.esc)
        finally:
            shutil.rmtree(cwd, ignore_errors=True)
