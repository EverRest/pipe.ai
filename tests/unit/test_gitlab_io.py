import json
import subprocess

import pytest

from pipe.gitlab_io import load_token, make_mr_state

URL = "https://git.example.com/grp/sub/proj/-/merge_requests/12"


def fake(status=200, body=None, boom=None):
    calls = []

    def http(url, headers):
        calls.append((url, headers))
        if boom:
            raise boom
        return status, body if body is not None else b"{}"

    http.calls = calls
    return http


def body(state):
    return json.dumps({"state": state, "merged_at": "2026-11-10T10:00:00Z", "title": "T"}).encode()


def test_maps_state_and_request():
    h = fake(body=body("opened"))
    r = make_mr_state("https://git.example.com", "tok", h)(URL)
    assert r == {"state": "open", "merged_at": "2026-11-10T10:00:00Z"}
    url, headers = h.calls[0]
    assert url == "https://git.example.com/api/v4/projects/grp%2Fsub%2Fproj/merge_requests/12"
    assert headers == {"PRIVATE-TOKEN": "tok"}
    assert (
        make_mr_state("https://git.example.com", "t", fake(body=body("merged")))(URL)["state"]
        == "merged"
    )


def test_other_host_no_request():
    h = fake()
    assert (
        make_mr_state("https://git.example.com", "tok", h)("https://evil.io/a/-/merge_requests/1")
        is None
    )
    assert h.calls == []


@pytest.mark.parametrize(
    "h", [fake(404), fake(boom=TimeoutError("tok")), fake(body=b"not json"), fake(body=b"[]")]
)
def test_failures_give_none(h):
    assert make_mr_state("https://git.example.com", "tok", h)(URL) is None


def test_needs_https():
    with pytest.raises(ValueError):
        make_mr_state("http://git.example.com", "tok", fake())


def test_load_token_env_first_then_keychain():
    assert load_token("svc", env={"PIPE_GITLAB_TOKEN": "e"}) == "e"
    calls = []

    def run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "k\n", "")

    assert load_token("svc", env={}, run=run) == "k"
    assert calls == [["security", "find-generic-password", "-s", "svc", "-a", "token", "-w"]]


def test_load_token_failure_hides_token():
    def run(cmd):
        return subprocess.CompletedProcess(cmd, 44, "", "secret-stderr")

    with pytest.raises(RuntimeError) as e:
        load_token("svc", env={}, run=run)
    assert "secret" not in str(e.value)
