"""Read-only GitLab MR state (first MrState provider). The token is never printed."""

import json
import os
import re
import subprocess
import urllib.request
from urllib.parse import quote, urlparse

_MR = re.compile(r"^/(.+?)(?:/-)?/merge_requests/(\d+)")
_STATE = {"opened": "open", "locked": "open", "merged": "merged", "closed": "closed"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # a redirect could carry the token to another host


def _http(url, headers):
    req = urllib.request.Request(url, headers=headers)  # noqa: S310 (https checked)
    with urllib.request.build_opener(_NoRedirect).open(req, timeout=10) as r:
        return r.status, r.read()


def load_token(service, env=os.environ, run=None):
    """Env `PIPE_GITLAB_TOKEN`, else Keychain item (service, account `token`)."""
    if env.get("PIPE_GITLAB_TOKEN"):
        return env["PIPE_GITLAB_TOKEN"]
    run = run or (lambda c: subprocess.run(c, capture_output=True, text=True, check=False))  # noqa: S603
    r = run(["security", "find-generic-password", "-s", service, "-a", "token", "-w"])
    if r.returncode != 0:
        raise RuntimeError(f"keychain item not found: service={service} account=token")
    return r.stdout.strip()


def make_mr_state(base_url, token, http=_http):
    """Return `mr_state(url) -> {state, merged_at} | None`. Sends the token to `base_url` only."""
    base = urlparse(base_url)
    if base.scheme != "https":
        raise ValueError("GitLab URL must be https")

    def mr_state(url):
        u = urlparse(url)
        m = _MR.match(u.path)
        if u.scheme != "https" or u.netloc.lower() != base.netloc.lower() or not m:
            return None
        api = f"{base.scheme}://{base.netloc}/api/v4/projects/{quote(m[1], safe='')}"
        try:
            status, raw = http(f"{api}/merge_requests/{m[2]}", {"PRIVATE-TOKEN": token})
            d = json.loads(raw)
            if status != 200:
                return None
            return {"state": _STATE[d["state"]], "merged_at": d.get("merged_at")}
        except Exception:  # noqa: BLE001 (any failure means unknown; no error text)
            return None

    return mr_state
