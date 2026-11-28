"""`pipe` command dispatcher. Sub-commands are stubs until later phases."""

import argparse
import contextlib
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipe")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("doctor")
    sub.add_parser("capabilities")
    s = sub.add_parser("schedule")
    s.add_argument("--install", action="store_true")
    s.add_argument("--remove", action="store_true")
    h = sub.add_parser("status-hook")
    h.add_argument("event", choices=["SessionStart", "Stop", "SessionEnd"])
    sub.add_parser("metrics", add_help=False)  # its own args go to metrics_cli
    f = sub.add_parser("flows")
    f.add_argument("action", nargs="?", choices=["show", "validate"])
    f.add_argument("name", nargs="?")
    return p


class _Router:
    """Declared `exec:`/`http:` capabilities go to their runtime; the rest to Claude."""

    def __init__(self, default, by_prefix):
        self.default, self.by_prefix = default, by_prefix

    def run(self, inp):
        ids = tuple(getattr(inp.request, "capabilities", None) or ())
        rt = self.by_prefix.get(ids[0].split(":")[0]) if len(ids) == 1 else None
        return (rt or self.default).run(inp)


def _build_runtime(cfg, default, read_cap_token, scrub=None, esc=lambda s: s, **http_kw):
    from pipe.core.scrub import scrub as _scrub
    from pipe.runtime_exec import ExecRuntime
    from pipe.runtime_http import HttpRuntime

    scrub = scrub or _scrub
    # read_token takes (service, account); a declared token is always account `token`.
    http = HttpRuntime(
        cfg, read_token=lambda svc, _acct: read_cap_token(svc), scrub=scrub, escape_mentions=esc,
        **http_kw,
    )  # fmt: skip
    ex = ExecRuntime(cfg, scrub=scrub, escape_mentions=esc)
    return _Router(default, {"http": http, "exec": ex})


def _sweep(cfg) -> None:
    """Drop stale worktrees from a crashed run. Never stops the adapter."""
    import logging
    import time

    from pipe.git_io import Git, sweep_worktrees

    try:
        repos = list(cfg.delegate_repos.values())
        sweep_worktrees(Git(), repos, cfg.worktree_root, time.time())
    except Exception:
        logging.getLogger(__name__).exception("worktree sweep failed")


def _run_adapter() -> int:
    """Composition root for `pipe run`: the only place that names the Slack transport."""
    from slack_sdk import WebClient

    from pipe import adapter
    from pipe.config import load_config
    from pipe.core.scrub import scrub
    from pipe.keychain import read_capability_token, read_token
    from pipe.runtime_claude import ClaudeRuntime
    from pipe.transport_slack import SlackTransport

    cfg = load_config()
    service = cfg.slack_tokens.removeprefix("keychain:")
    bot, app = read_token(service, "bot"), read_token(service, "app")
    t = SlackTransport(WebClient(token=bot), scrub=scrub)
    # The adapter escapes the reply once; the runtime only scrubs (no double escape).
    rt = ClaudeRuntime(cfg, scrub=scrub, escape_mentions=lambda s: s)
    rt = _build_runtime(cfg, rt, read_capability_token, scrub)
    _sweep(cfg)
    adapter.run_forever(cfg, t, rt, scrub, t.escape_mentions, lambda: t.connect(bot, app))
    return 0


def _mr_state_reader(cfg, load_token, make):
    """GitLab MR-state reader from `cfg.mr_state`, or None when it is not set."""
    gl = (cfg.mr_state or {}).get("gitlab")
    return make(gl["url"], load_token(gl["token"].removeprefix("keychain:"))) if gl else None


def _metrics_args(cfg, argv):
    return argv if "--channel" in argv else ["--channel", cfg.work_channel, *argv]


def _run_metrics(argv: list[str]) -> int:
    """Composition root for `pipe metrics`: Slack reader plus the optional GitLab MR state."""
    from slack_sdk import WebClient

    from pipe import gitlab_io, metrics_cli
    from pipe.config import load_config
    from pipe.core.scrub import scrub
    from pipe.keychain import read_token
    from pipe.transport_slack import SlackTransport

    cfg = load_config()
    reader = SlackTransport(
        WebClient(token=read_token(cfg.slack_tokens.removeprefix("keychain:"), "bot")), scrub=scrub
    )
    gitlab = _mr_state_reader(cfg, gitlab_io.load_token, gitlab_io.make_mr_state)
    return metrics_cli.main(_metrics_args(cfg, argv), reader, gitlab)


def _default_load():
    """Return (flows, errors) from the flow files. Import is deferred (spec 006 modules)."""
    from pipe import flows_io

    shared = Path(__file__).resolve().parents[2] / "flows"
    vocab = flows_io.load_tags(shared / "tags.yaml")
    errors: list[str] = []
    flows = flows_io.load_flows(shared, Path("~/.pipe/flows").expanduser(), vocab, errors=errors)
    return flows, errors


def _step(st, key):
    """Read a step field from a dict step (the core form) or an object step."""
    return st.get(key) if isinstance(st, dict) else getattr(st, key, None)


def make_flows_handler(load):
    """Build `flows_handler(action, name) -> int`.

    `load()` returns `({name: Flow}, [error str])`.
    """

    def handler(action, name):
        flows, errors = load()
        bad = [e for e in errors if not name or e.startswith(name)]
        if name and name not in flows and not bad or action == "show" and name not in flows:
            print("unknown flow")
            return 1
        if action == "show":
            f = flows[name]
            print(f"{f.name}: {f.description}")
            for i, st in enumerate(f.steps):
                cap = _step(st, "capability") or "human"
                print(f"{i} {_step(st, 'id')} {cap} {_step(st, 'access')} {_step(st, 'goal')}")
            return 0
        if action == "validate":
            for n in sorted(flows):
                if not name or n == name:
                    print(f"ok {n}")
            for e in bad:
                print(e)
            return 1 if bad else 0
        for n in sorted(flows):  # list
            f = flows[n]
            agents = sum(_step(st, "capability") is not None for st in f.steps)
            print(f"{n}  {f.description}  {agents}")
        return 1 if errors else 0

    return handler


def flows_handler(action, name):
    try:
        return make_flows_handler(_default_load)(action, name)
    except ImportError:
        print("flows: not installed")
        return 1


def main(
    argv=None, flows_handler=flows_handler, run_handler=_run_adapter, metrics_handler=_run_metrics
):
    """Run the CLI. `flows_handler(action, name) -> int` is injected by spec 006.

    `run_handler() -> int` starts the adapter; tests inject a fake.
    """
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["metrics"]:
        return metrics_handler(argv[1:])
    p = _parser()
    a = p.parse_args(argv)
    if a.cmd == "flows":
        if a.action == "show" and not a.name:
            p.error("flows show needs a name")
        if a.action is None and a.name:
            p.error("unexpected argument")
        return flows_handler(a.action or "list", a.name)
    if a.cmd == "status-hook":
        from pipe import hook

        with contextlib.suppress(BaseException):  # the hook must never fail
            hook.main(a.event)
        return 0
    if a.cmd == "run":
        return run_handler()
    if a.cmd == "capabilities":
        from pipe.capset import collect
        from pipe.config import load_config
        from pipe.core.exposure import render_list

        cfg = load_config()
        caps, notes = collect(cfg)
        print("\n".join(render_list(caps, cfg.exposed, notes)))
        return 0
    if a.cmd == "doctor":
        from pipe import doctor

        probs = doctor.check()
        for x in probs:
            print(f"FAIL {x}")
        print("PASS all checks" if not probs else f"{len(probs)} problem(s)")
        return 1 if probs else 0
    if a.cmd == "schedule" and (a.install or a.remove):
        import subprocess

        from pipe import launchd

        def run(cmd):
            return subprocess.run(cmd, check=False).returncode  # noqa: S603

        return int((launchd.install if a.install else launchd.remove)(run) != 0)
    print(f"pipe {a.cmd}: not implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
