"""wiz-review wrapper for an exec capability. Stdlib only.

stdin: effective payload JSON. stdout: one JSON result. Exit 0 also for a
runtime `failed` status. Env: WIZ_REVIEW_URL, WIZ_REVIEW_TOKEN (never printed),
WIZ_REVIEW_GITLAB_HOST (the only host a change link may use), optional
WIZ_REVIEW_MAX_WAIT_S (default 3600).
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request

POLL_S = 15
SECRET = re.compile(r"(xox[a-z]-|xapp-|glpat-|Bearer\s+)\S*")


def find_link(payload):
    """mr_url, else the first https link of artifacts, else None."""
    u = payload.get("mr_url")
    if isinstance(u, str) and u.startswith("https://"):
        return u
    for a in payload.get("artifacts") or []:
        if isinstance(a, str) and a.startswith("https://"):
            return a
    return None


MR_PATH = re.compile(r"^/[A-Za-z0-9_.~/-]+/merge_requests/[0-9]+$")


def clean_link(link, host):
    """Return a rebuilt https MR link on `host`, or None.

    Refuse backslash, userinfo, whitespace, control characters, a port, and any
    path that is not a merge request. Send only the rebuilt link, never the raw one.
    """
    if not isinstance(link, str) or re.search(r"[\\\s\x00-\x1f\x7f@]", link):
        return None
    try:
        u = urllib.parse.urlparse(link)
        port = u.port
    except ValueError:
        return None
    if u.scheme != "https" or u.username or u.password or port is not None:
        return None
    if not u.hostname or u.hostname != host.lower() or not MR_PATH.match(u.path):
        return None
    return urllib.parse.urlunparse(("https", u.hostname, u.path, "", "", ""))


def scrub(s, token=""):
    s = s.replace(token, "[redacted]") if token else s
    return SECRET.sub("[redacted]", s)


def http_json(method, url, token, body=None):
    req = urllib.request.Request(  # noqa: S310 (scheme checked in run)
        url,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return json.load(r)


def run(payload, env, http=http_json, sleep=time.sleep, now=time.monotonic):
    """Return (exit_code, result dict)."""
    tok = env.get("WIZ_REVIEW_TOKEN", "")
    fail = lambda rc, t: (rc, {"text": scrub(t, tok)})  # noqa: E731
    for k in ("WIZ_REVIEW_URL", "WIZ_REVIEW_TOKEN", "WIZ_REVIEW_GITLAB_HOST"):
        if not env.get(k):
            return fail(2, f"missing environment variable {k}")
    base = env["WIZ_REVIEW_URL"].rstrip("/")
    u = urllib.parse.urlparse(base)
    if u.scheme != "https" and not (
        u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1")
    ):
        return fail(2, "WIZ_REVIEW_URL must be https")
    link = find_link(payload)
    if not link:
        return fail(2, "missing change link")
    link = clean_link(link, env["WIZ_REVIEW_GITLAB_HOST"])
    if not link:
        return fail(2, "change link is not on the GitLab host")
    q = f"{base}/reviews?url={urllib.parse.quote(link, safe='')}"
    deadline = now() + int(env.get("WIZ_REVIEW_MAX_WAIT_S") or 3600)
    try:
        st = http("GET", q, tok)
        if st.get("state") == "none":  # state first: a retry sends no second request
            http("POST", f"{base}/reviews", tok, {"url": link})
            st = {"state": "pending"}
        while st.get("state") not in ("ready", "error"):
            if now() >= deadline:
                return fail(1, "timed out waiting for wiz-review")
            sleep(POLL_S)
            st = http("GET", q, tok)
    except Exception as e:  # noqa: BLE001
        return fail(1, f"wiz-review request failed: {type(e).__name__} {e}")
    if st["state"] == "error":
        return 0, {"status": "failed", "text": scrub(str(st.get("reason") or "review failed"), tok)}
    arts = [a for a in st.get("drafts") or [] if isinstance(a, str) and a.startswith("https://")]
    return 0, {
        "status": "done",
        "text": scrub(str(st.get("text") or "drafts ready"), tok),
        "artifacts": arts,
    }


def main(argv):
    import os

    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    rc, out = run(payload if isinstance(payload, dict) else {}, os.environ)
    if rc:
        print(out["text"], file=sys.stderr)
    print(json.dumps(out))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
