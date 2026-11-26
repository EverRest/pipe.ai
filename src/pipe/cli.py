"""`pipe` command dispatcher. Sub-commands are stubs until later phases."""

import argparse
import sys


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipe")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("doctor")
    s = sub.add_parser("schedule")
    s.add_argument("--install", action="store_true")
    s.add_argument("--remove", action="store_true")
    h = sub.add_parser("status-hook")
    h.add_argument("event", choices=["SessionStart", "Stop", "SessionEnd"])
    f = sub.add_parser("flows")
    f.add_argument("action", nargs="?", choices=["show", "validate"])
    f.add_argument("name", nargs="?")
    return p


def main(argv=None, flows_handler=None) -> int:
    """Run the CLI. `flows_handler(action, name) -> int` is injected by spec 006."""
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
    print(f"pipe {a.cmd}: not implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
