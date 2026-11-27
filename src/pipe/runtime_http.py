"""RuntimePort for a declared `http` capability (contracts/runtime-exec-http.md)."""

import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlparse

from pipe.core.contract import RuntimeFailed, RuntimeInput, RuntimeOutput
from pipe.core.scrub import scrub as _scrub
from pipe.runtime_exec import MAX_OUT, build_input, find_entry, finish

log = logging.getLogger(__name__)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # the 3xx then raises HTTPError


def urllib_transport(url, headers, body, timeout):
    """-> (status, body bytes). Never follows a redirect."""
    req = urllib.request.Request(url, body, headers, method="POST")  # noqa: S310 (scheme checked in config)
    op = urllib.request.build_opener(NoRedirect)
    try:
        with op.open(req, timeout=timeout) as r:
            return r.status, r.read(MAX_OUT + 1)
    except urllib.error.HTTPError as e:
        return e.code, b""


def _no_token(service, account):
    raise RuntimeFailed("token not available")


class HttpRuntime:
    def __init__(
        self,
        cfg,
        transport=urllib_transport,
        read_token: Callable[[str, str], str] = _no_token,
        scrub: Callable = _scrub,
        escape_mentions: Callable = lambda s: s,
    ):
        self.cfg, self.transport, self.read_token = cfg, transport, read_token
        self.scrub, self.esc = scrub, escape_mentions

    def run(self, inp: RuntimeInput) -> RuntimeOutput:
        e = find_entry(self.cfg, inp, "http")
        headers = {"Content-Type": "application/json"}
        secrets = ()
        if e.get("token"):
            try:
                tok = self.read_token(e["token"].removeprefix("keychain:"), "token")
            except Exception:
                raise RuntimeFailed("token not available") from None
            headers["Authorization"] = f"Bearer {tok}"
            secrets = (tok,)
        host = urlparse(e["url"]).hostname
        timeout = e.get("timeout_s", self.cfg.step_timeout_min * 60)
        try:
            status, body = self.transport(e["url"], headers, build_input(inp).encode(), timeout)
        except TimeoutError:
            raise RuntimeFailed("timeout") from None
        except OSError:
            raise RuntimeFailed("http error") from None
        log.info("http %s host=%s status=%s", e["id"], host, status)
        if not 200 <= status < 300:
            raise RuntimeFailed(f"http {status}")
        if len(body) > MAX_OUT:
            raise RuntimeFailed("result too large")
        scrub = lambda s: self.scrub(s, secrets)  # noqa: E731
        return finish(body.decode("utf-8", "replace"), scrub, self.esc)
