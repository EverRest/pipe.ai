"""`pipe` command dispatcher. Sub-commands are stubs until later phases."""

import argparse
import contextlib
import sys


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


def _run_adapter() -> int:
    """Composition root for `pipe run`: the only place that names the Slack transport."""
    from slack_sdk import WebClient

    from pipe import adapter
    from pipe.config import load_config
    from pipe.core.scrub import scrub
    from pipe.keychain import read_token
    from pipe.runtime_claude import ClaudeRuntime
    from pipe.transport_slack import SlackTransport

    cfg = load_config()
    service = cfg.slack_tokens.removeprefix("keychain:")
    bot, app = read_token(service, "bot"), read_token(service, "app")
    t = SlackTransport(WebClient(token=bot), scrub=scrub)
    # The adapter escapes the reply once; the runtime only scrubs (no double escape).
    rt = ClaudeRuntime(cfg, scrub=scrub, escape_mentions=lambda s: s)
    adapter.run_forever(cfg, t, rt, scrub, t.escape_mentions, lambda: t.connect(bot, app))
    return 0


def _run_metrics(argv: list[str]) -> int:
    """Composition root for `pipe metrics`: Slack reader plus the optional GitLab MR state."""
    import yaml
    from slack_sdk import WebClient

    from pipe import gitlab_io, metrics_cli
    from pipe.config import load_config
    from pipe.core.scrub import scrub
    from pipe.keychain import read_token
    from pipe.state import pipe_home
    from pipe.transport_slack import SlackTransport

    cfg = load_config()
    reader = SlackTransport(
        WebClient(token=read_token(cfg.slack_tokens.removeprefix("keychain:"), "bot")), scrub=scrub
    )
    # `mr_state.gitlab` is read here until the config module validates it (T006).
    gl = (yaml.safe_load((pipe_home() / "config.yaml").read_text()).get("mr_state") or {}).get(
        "gitlab"
    ) or {}
    gitlab = None
    if gl.get("url") and str(gl.get("token", "")).startswith("keychain:"):
        token = gitlab_io.load_token(gl["token"].removeprefix("keychain:"))
        gitlab = gitlab_io.make_mr_state(gl["url"], token)
    return metrics_cli.main(argv, reader, gitlab)


def main(argv=None, flows_handler=None, run_handler=_run_adapter, metrics_handler=_run_metrics):
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
        if flows_handler is None:
            print("flows: not installed")
            return 1
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
