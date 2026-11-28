"""RuntimePort over `claude -p` (contracts/runtime-contract.md). The runner is injected."""

import json
import logging
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

from pipe.config import Config
from pipe.core.contract import RuntimeFailed, RuntimeInput, RuntimeOutput, parse_output
from pipe.git_io import Git
from pipe.planner import PLAN_SCHEMA
from pipe.runtime_claude_cmd import (  # re-exported: tests and callers import from here
    ENV_KEEP as ENV_KEEP,
)
from pipe.runtime_claude_cmd import (
    PATH_TOOLS as PATH_TOOLS,
)
from pipe.runtime_claude_cmd import (
    SCHEMA,
    _child_env,
    _payload,
    _roots,
    build_cmd,
    build_prompt,
)
from pipe.runtime_claude_delegate import run_write
from pipe.runtime_claude_discovery import discover, read_mcp_entries
from pipe.runtime_claude_load import PreparedLoad, cleanup, prepare
from pipe.runtime_claude_loadset import LoadSet
from pipe.runtime_claude_request import map_request
from pipe.runtime_claude_tools import tools_for
from pipe.state import pipe_home

log = logging.getLogger(__name__)

# runner(argv, stdin, env, cwd, timeout_s) -> (returncode, stdout)
Runner = Callable[[list[str], str, dict, str, float], tuple[int, str]]


def subprocess_runner(argv, stdin, env, cwd, timeout):
    p = subprocess.run(  # noqa: S603 (argv list, no shell)
        argv, input=stdin, env=env, cwd=cwd, timeout=timeout, capture_output=True, text=True
    )
    return p.returncode, p.stdout


def _plan_data(stdout: str) -> dict:
    """A plan run returns the schema object as `data`; the planner checks it."""
    try:
        raw = json.loads(_payload(stdout))
    except ValueError as e:
        raise RuntimeFailed("invalid plan output") from e
    if not isinstance(raw, dict):
        raise RuntimeFailed("invalid plan output")
    return raw


class ClaudeRuntime:
    def __init__(
        self,
        cfg: Config,
        runner: Runner = subprocess_runner,
        scrub: Callable[[str], str] = lambda s: s,
        escape_mentions: Callable[[str], str] = lambda s: s,
        prepare: Callable = prepare,
        home: Path | None = None,
        git: Git | None = None,
    ):
        self.cfg, self.runner, self.scrub, self.esc = cfg, runner, scrub, escape_mentions
        self.prepare, self.home = prepare, home
        self.git = git or Git()

    def _load(self, ls: LoadSet | None, run_dir: Path) -> PreparedLoad | None:
        """Load only the exposed items of this step. None means a stage 001 run."""
        if ls is None:
            return None
        for n in ls.skipped:
            log.info("%s", n.text)  # id only, no path
        if not (ls.skills or ls.commands or ls.mcp):
            return None
        return self.prepare(ls, run_dir, read_mcp_entries(self.home or Path.home()))

    def run(self, inp: RuntimeInput) -> RuntimeOutput:
        cfg = self.cfg
        req = inp.request
        home = self.home or Path.home()
        if getattr(req, "access", None) == "write":
            caps, _ = discover(home, cfg.repo_roots)
            return run_write(
                inp, cfg, self.git, self.runner, caps, self.scrub, self.esc, self.prepare, home
            )
        if req is None:  # chat: no capability, the owner's tools only
            pol, ls = tools_for(inp.requester_is_owner, cfg.owner_tools, cfg.deny_rules), None
        else:
            caps, _ = discover(home, cfg.repo_roots)
            st = map_request(req, cfg, caps)
            pol, ls = st.policy, st.load
        cwd = _roots(cfg)[0]
        run_dir = pipe_home() / "run" / uuid.uuid4().hex
        # Only a run with capability IDs creates a load directory (it may hold MCP config).
        loads = bool(req and req.capabilities)
        is_plan = inp.task.get("purpose") == "plan"
        schema = json.dumps(PLAN_SCHEMA) if is_plan else SCHEMA
        try:
            prepared = self._load(ls, run_dir)
            code, out = self.runner(
                build_cmd(cfg, pol, prepared, schema=schema, settings=not inp.requester_is_owner),
                build_prompt(inp.thread, inp.task),
                _child_env(),
                cwd,
                cfg.step_timeout_min * 60,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeFailed("timeout") from e
        except FileNotFoundError as e:
            raise RuntimeFailed("command not found") from e
        finally:
            if loads:
                cleanup(run_dir)
        if code != 0:
            raise RuntimeFailed(f"exit {code}")
        if is_plan:
            return RuntimeOutput(text="", data=_plan_data(out))
        o = parse_output(_payload(out))
        return RuntimeOutput(
            text=self.esc(self.scrub(o.text)),
            status=o.status,
            reason=self.scrub(o.reason) if o.reason else o.reason,
            proposal=o.proposal,
            next=o.next,
            artifacts=[self.scrub(a) for a in o.artifacts],
            data=o.data,
        )
