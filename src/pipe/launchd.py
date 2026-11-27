"""launchd job for the adapter: plist text, install, remove. launchctl is injected."""

import os
import plistlib
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

from pipe.state import pipe_home

LABEL = "com.pipe-ai.adapter"


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _launcher() -> str:
    return str(pipe_home() / "bin" / "pipe")


def write_launcher(path, python=None) -> None:
    """Shell script that runs the venv Python; absolute paths, no PATH lookup, no secrets."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nexec {shlex.quote(python or sys.executable)} -m pipe.cli run\n")
    path.chmod(0o700)


def plist_text(launcher: str, log: str) -> str:
    return plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": [launcher, "run"],
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "StandardOutPath": log,
            "StandardErrorPath": log,
        }
    ).decode()


def plist_is_current(path: Path, launcher: str) -> bool:
    try:
        return plistlib.loads(path.read_bytes())["ProgramArguments"][0] == launcher
    except OSError, KeyError, IndexError, plistlib.InvalidFileException:
        return False


def install(run: Callable, plist_path=None, uid=None, launcher=None) -> int:
    path, uid, launcher = plist_path or _plist_path(), uid or os.getuid(), launcher or _launcher()
    write_launcher(launcher)
    log = pipe_home() / "logs" / "adapter.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plist_text(launcher, str(log)))
    return run(["launchctl", "bootstrap", f"gui/{uid}", str(path)])


def remove(run: Callable, plist_path=None, uid=None) -> int:
    path, uid = plist_path or _plist_path(), uid or os.getuid()
    rc = run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])
    path.unlink(missing_ok=True)
    return rc


def is_loaded(run: Callable, uid=None) -> bool:
    return run(["launchctl", "print", f"gui/{uid or os.getuid()}/{LABEL}"]) == 0
