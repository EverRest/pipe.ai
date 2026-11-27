import json
import logging
from types import SimpleNamespace as NS

import pytest

from pipe.core.contract import RuntimeFailed, RuntimeInput
from pipe.runtime_http import HttpRuntime

OK = json.dumps({"text": "hi", "status": "done"}).encode()
URL = "https://api.example/secret/path?q=1"
ENTRY = {
    "id": "h", "runtime": "http", "name": "H", "description": "d", "access": "read",
    "url": URL, "token": "keychain:svc", "timeout_s": 7,
}  # fmt: skip


def cfg(exposed=("http:h",), entry=ENTRY):
    return NS(capabilities=[entry], exposed=list(exposed), step_timeout_min=30)


def inp(caps=("http:h",), owner=True, schema=None, payload=None):
    task = {"id": "T1", "purpose": "step", "step": 2, "pipeline": {"goal": "g"}}
    if payload is not None:
        task["payload"] = payload
    req = NS(capabilities=caps, access="read", requester_is_owner=owner, output_schema=schema)
    return RuntimeInput(thread=[], task=task, requester_is_owner=owner, request=req)


class Transport:
    def __init__(self, status=200, body=OK, exc=None):
        self.status, self.body, self.exc, self.calls = status, body, exc, []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(NS(url=url, headers=headers, body=body, timeout=timeout))
        if self.exc:
            raise self.exc
        return self.status, self.body


def reader(service, account):
    assert (service, account) == ("svc", "token")
    return "tok-1234567890abcdef"


def rt(t, c=None, **kw):
    return HttpRuntime(c or cfg(), transport=t, read_token=reader, **kw)


def test_post_json_and_bearer():
    t = Transport()
    o = rt(t).run(inp(schema={"type": "object"}, payload={"a": 1}))
    c = t.calls[0]
    assert o.text == "hi" and c.url == URL and c.timeout == 7
    assert c.headers["Content-Type"] == "application/json"
    assert c.headers["Authorization"] == "Bearer tok-1234567890abcdef"
    assert json.loads(c.body) == {
        "goal": "g", "payload": {"a": 1}, "task": {"id": "T1", "step": 2},
        "output_schema": {"type": "object"},
    }  # fmt: skip


def test_no_token_no_header():
    e = {k: v for k, v in ENTRY.items() if k != "token"}
    t = Transport()
    rt(t, cfg(entry=e)).run(inp())
    assert "Authorization" not in t.calls[0].headers


def test_token_read_failure_hides_detail():
    def bad(service, account):
        raise RuntimeError("keychain boom tok-1234567890abcdef")

    with pytest.raises(RuntimeFailed) as e:
        HttpRuntime(cfg(), transport=Transport(), read_token=bad).run(inp())
    assert "boom" not in str(e.value) and "tok-" not in str(e.value)


@pytest.mark.parametrize("code", [302, 301, 404, 500, 199, 300])
def test_status_codes(code):
    with pytest.raises(RuntimeFailed) as e:
        rt(Transport(status=code)).run(inp())
    assert str(e.value) == f"http {code}"


@pytest.mark.parametrize("body", [b"nope", b'{"status":"done"}', b'{"text":"x","status":"zz"}'])
def test_bad_body(body):
    with pytest.raises(RuntimeFailed):
        rt(Transport(body=body)).run(inp())


def test_too_large():
    big = json.dumps({"text": "x" * 1_100_000, "status": "done"}).encode()
    with pytest.raises(RuntimeFailed, match="result too large"):
        rt(Transport(body=big)).run(inp())


def test_timeout_and_error():
    with pytest.raises(RuntimeFailed, match="timeout"):
        rt(Transport(exc=TimeoutError())).run(inp())
    with pytest.raises(RuntimeFailed, match="http error") as e:
        rt(Transport(exc=OSError(URL))).run(inp())
    assert "secret" not in str(e.value)


def test_scrub_escape_artifacts():
    body = json.dumps(
        {
            "text": "xoxb-abcdefghij <!here>",
            "status": "done",
            "artifacts": ["http://x", "https://y"],
        }
    ).encode()
    o = rt(Transport(body=body), escape_mentions=lambda s: s.replace("<!", "<\\!")).run(inp())
    assert o.text == "[redacted] <\\!here>" and o.artifacts == ["https://y"]


@pytest.mark.parametrize("owner", [True, False])
def test_refused_not_exposed(owner):
    t = Transport()
    with pytest.raises(RuntimeFailed, match="capability not available"):
        rt(t, cfg(exposed=())).run(inp(owner=owner))
    assert t.calls == []


def test_no_url_path_or_token_in_log(caplog):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(RuntimeFailed) as e:
        rt(Transport(status=500)).run(inp())
    text = caplog.text + str(e.value)
    assert "secret" not in text and "q=1" not in text and "tok-1234567890abcdef" not in text


def test_redirect_handler_refuses():
    from pipe.runtime_http import NoRedirect

    assert NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://x") is None
