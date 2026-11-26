"""Secret scrub. Pure."""

import re

SECRET_RES = [
    re.compile(r"xox[abposr]-[A-Za-z0-9-]{5,}"),  # Slack bot, user, other
    re.compile(r"xapp-[A-Za-z0-9-]{5,}"),  # Slack app-level
    re.compile(r"glpat-[A-Za-z0-9_-]{10,}"),  # GitLab PAT
    re.compile(r"gl[a-z]{2,3}-[A-Za-z0-9_-]{20,}"),  # other GitLab tokens
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),  # API keys
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS key id
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
]


def scrub(text: str, secrets: tuple[str, ...] | list[str] = ()) -> str:
    """Replace token-like strings and the exact `secrets` values with [redacted]."""
    for s in secrets:
        if s:
            text = text.replace(s, "[redacted]")
    for r in SECRET_RES:
        text = r.sub("[redacted]", text)
    return text
