"""GitLab MR link from `git push` output. Pure: no network, no token."""

import re
from urllib.parse import urlparse

_MR_URL = re.compile(r"https?://\S+/merge_requests/\d+")


def mr_link_from_push(output_text, base_url):
    """First `https://` MR link on the `base_url` host in push output, else None."""
    base = urlparse(base_url) if isinstance(base_url, str) else None
    if not base or base.scheme != "https" or not base.hostname or not isinstance(output_text, str):
        return None
    for m in _MR_URL.finditer(output_text):
        u = urlparse(m[0])
        if u.scheme == "https" and u.netloc.lower() == base.netloc.lower():
            return m[0]
    return None
