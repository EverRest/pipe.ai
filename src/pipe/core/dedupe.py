"""Seen-set update. Pure."""


def remember(keys: list[str], new: str, limit: int = 500) -> list[str]:
    """Return a new list with `new` added; keep the last `limit`."""
    return ([*keys, new] if new not in keys else list(keys))[-limit:]
