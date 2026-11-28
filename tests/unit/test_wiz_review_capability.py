import importlib.util
import json
from pathlib import Path

import pytest

P = Path(__file__).resolve().parents[2] / "templates/review/wiz_review_capability.py"
spec = importlib.util.spec_from_file_location("wiz_cap", P)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

TOKEN = "s3cret-tok-value"  # noqa: S105
ENV = {
    "WIZ_REVIEW_URL": "https://wiz.example/api",
    "WIZ_REVIEW_TOKEN": TOKEN,
    "WIZ_REVIEW_GITLAB_HOST": "gitlab.example",
}
MR = {"mr_url": "https://gitlab.example/g/p/-/merge_requests/1"}


class Http:
    """Fake HTTP: states is the list of GET replies; the last one repeats."""

    def __init__(self, states):
        self.states, self.calls = list(states), []

    def __call__(self, method, url, token, body=None):
        self.calls.append((method, url, token, body))
        if method == "POST":
            return {"id": "r1"}
        s = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return s if isinstance(s, dict) else {"state": s}


class Clock:
    def __init__(self):
        self.t, self.sleeps = 0.0, []

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def now(self):
        return self.t


def go(payload, http, env=ENV, clock=None):
    c = clock or Clock()
    return w.run(payload, env, http, c.sleep, c.now), c


def posts(h):
    return [x for x in h.calls if x[0] == "POST"]


def test_find_link():
    assert w.find_link(MR) == MR["mr_url"]
    assert w.find_link({"artifacts": ["ftp://x", "https://a/b"]}) == "https://a/b"
    assert w.find_link({"mr_url": "http://x"}) is None
    assert w.find_link({}) is None


def test_missing_link_exit_2_no_http():
    h = Http(["none"])
    (rc, out), _ = go({}, h)
    assert rc == 2 and out["text"] == "missing change link" and not h.calls


def test_none_sends_one_request_then_polls_until_ready():
    h = Http(
        [
            "none",
            "pending",
            "pending",
            {"state": "ready", "text": "3 drafts", "drafts": ["https://d/1"]},
        ]
    )
    (rc, out), c = go(MR, h)
    assert rc == 0 and len(posts(h)) == 1
    assert out == {"status": "done", "text": "3 drafts", "artifacts": ["https://d/1"]}
    assert c.sleeps == [15, 15, 15]


def test_pending_and_ready_send_no_request():
    h = Http(["pending", "ready"])
    go(MR, h)
    assert not posts(h)
    h = Http([{"state": "ready", "drafts": []}])
    (rc, _), c = go(MR, h)
    assert rc == 0 and not posts(h) and not c.sleeps


def test_second_drafts_ready_ignored():
    # a retry after done: state is ready again, no second request
    h = Http(["ready"])
    go(MR, h)
    go(MR, h)
    assert not posts(h)


def test_error_state_is_failed_status_exit_0():
    h = Http(["none", {"state": "error", "reason": f"boom {TOKEN} glpat-abcdefghij"}])
    (rc, out), _ = go(MR, h)
    assert rc == 0 and out["status"] == "failed"
    assert TOKEN not in out["text"] and "glpat-abcdefghij" not in out["text"]


def test_http_failure_is_nonzero_and_scrubbed():
    def bad(*a, **k):
        raise OSError(f"conn {TOKEN}")

    (rc, out), _ = go(MR, bad)
    assert rc == 1 and "status" not in out and TOKEN not in out["text"]


def test_wait_bound_stops_polling():
    (rc, out), c = go(MR, Http(["pending"]), env={**ENV, "WIZ_REVIEW_MAX_WAIT_S": "60"})
    assert rc == 1 and "timed out" in out["text"] and c.t <= 75


@pytest.mark.parametrize("env", [{}, {"WIZ_REVIEW_URL": ENV["WIZ_REVIEW_URL"]}])
def test_missing_env_names_variable(env):
    (rc, out), _ = go(MR, Http(["none"]), env=env)
    assert rc == 2 and "WIZ_REVIEW_" in out["text"]


@pytest.mark.parametrize("url", ["http://wiz.example/api", "ftp://x", "file:///etc"])
def test_https_only_except_localhost(url):
    h = Http(["none"])
    (rc, out), _ = go(MR, h, env={**ENV, "WIZ_REVIEW_URL": url})
    assert rc == 2 and not h.calls
    (rc, _), _ = go(MR, Http(["ready"]), env={**ENV, "WIZ_REVIEW_URL": "http://localhost:8080/api"})
    assert rc == 0


def test_link_on_other_host_refused_without_request():
    h = Http(["none"])
    (rc, out), _ = go({"mr_url": "https://evil.example/g/p/-/merge_requests/1"}, h)
    assert rc == 2 and "GitLab host" in out["text"] and not h.calls


def test_no_gitlab_host_refuses_without_request():
    h = Http(["none"])
    env = {k: v for k, v in ENV.items() if k != "WIZ_REVIEW_GITLAB_HOST"}
    (rc, out), _ = go(MR, h, env=env)
    assert rc == 2 and "WIZ_REVIEW_GITLAB_HOST" in out["text"] and not h.calls


def test_example_config_parses_with_array_context_and_exec_tag():
    import yaml

    ex = yaml.safe_load((P.parent / "config.example.yaml").read_text())
    cap = ex["capabilities"][0]
    assert f"{cap['runtime']}:{cap['id']}" in ex["tags"]
    assert cap["input_schema"]["properties"]["context"]["type"] == "array"
    assert "WIZ_REVIEW_GITLAB_HOST" in cap["env_allow"]


def test_artifacts_https_only():
    h = Http([{"state": "ready", "text": "t", "drafts": ["http://x", "https://ok", "file:///a"]}])
    (_, out), _ = go(MR, h)
    assert out["artifacts"] == ["https://ok"]


def test_token_in_header_only_never_printed(capsys, monkeypatch):
    h = Http(["none", "ready"])
    (rc, out), _ = go(MR, h)
    assert all(c[2] == TOKEN for c in h.calls)
    assert TOKEN not in json.dumps(out) and TOKEN not in json.dumps(
        [c[1:2] + c[3:] for c in h.calls]
    )
    monkeypatch.setattr(w, "run", lambda *a: (0, out))
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps(MR)))
    assert w.main([]) == 0
    assert TOKEN not in capsys.readouterr().out


@pytest.mark.parametrize(
    "link",
    [
        "https://gitlab.example\\@evil.example/g/p/-/merge_requests/1",  # backslash differential
        "https://gitlab.example@evil.example/g/p/-/merge_requests/1",  # userinfo
        "https://user:pw@gitlab.example/g/p/-/merge_requests/1",  # userinfo, right host
        "https://gitlab.example:8443/g/p/-/merge_requests/1",  # port
        "https://gitlab.example/g/p/-/merge_requests/1 \nX: y",  # whitespace and control
        "https://gitlab.example/g/p/-/issues/1",  # not a merge request
        "http://gitlab.example/g/p/-/merge_requests/1",  # not https
    ],
)
def test_tricky_links_are_refused_without_request(link):
    h = Http(["none"])
    (rc, out), _ = go({"mr_url": link}, h)
    assert rc == 2 and not h.calls


def test_only_the_rebuilt_link_is_sent():
    h = Http(["none", "ready"])
    link = "https://GitLab.Example/g/p/-/merge_requests/7?x=1#frag"
    (rc, _), _ = go({"mr_url": link}, h)
    assert rc == 0
    sent = " ".join(str(c[1]) + str(c[3]) for c in h.calls)
    assert "x%3D1" not in sent and "frag" not in sent
    assert "https%3A%2F%2Fgitlab.example%2Fg%2Fp%2F-%2Fmerge_requests%2F7" in sent
