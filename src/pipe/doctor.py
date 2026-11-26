"""Installation checks. Returns a list of problems (empty means all good)."""

import os
import stat
from collections.abc import Callable

from pipe.config import ConfigError, load_config
from pipe.keychain import ACCOUNTS, KeychainError, read_token
from pipe.state import pipe_home


def check(reader: Callable = read_token) -> list[str]:
    probs: list[str] = []
    home = pipe_home()
    if home.exists() and stat.S_IMODE(os.stat(home).st_mode) & 0o077:
        probs.append(f"directory mode: {home} is open to others. Run: chmod 700 {home}")
    try:
        cfg = load_config()
    except ConfigError as e:
        return [*probs, f"config: {e}"]
    service = cfg.slack_tokens.removeprefix("keychain:")
    for acct in ACCOUNTS:
        try:
            reader(service, acct)
        except KeychainError:
            probs.append(
                f"token: no Keychain item for service {service}, account {acct}. "
                f"Run: security add-generic-password -s {service} -a {acct} -w <token>"
            )
    if not cfg.owner:
        probs.append(
            "owner: config key owner is empty. Set owner to your Slack user ID in config.yaml"
        )
    return probs
