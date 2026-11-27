"""Read Slack tokens from the macOS Keychain. Never logs a token."""

import subprocess
from collections.abc import Callable

ACCOUNTS = ("bot", "app")


class KeychainError(Exception):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603


def read_token(service: str, account: str, run: Callable = _run) -> str:
    if account not in ACCOUNTS:
        raise ValueError(f"account must be one of {ACCOUNTS}")
    r = run(["security", "find-generic-password", "-s", service, "-a", account, "-w"])
    if r.returncode != 0:
        raise KeychainError(f"keychain item not found: service={service} account={account}")
    return r.stdout.strip()


def read_capability_token(service: str, run: Callable = _run) -> str:
    """Token of a declared `http` capability: Keychain item (service, account `token`)."""
    r = run(["security", "find-generic-password", "-s", service, "-a", "token", "-w"])
    if r.returncode != 0:
        raise KeychainError(f"keychain item not found: service={service}")
    return r.stdout.strip()
