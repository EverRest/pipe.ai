"""Tests for templates/trigger/post_trigger.py (fake HTTP, no network)."""

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "post_trigger", ROOT / "templates/trigger/post_trigger.py"
)
pt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pt)

TOKEN = "xoxb-" + "1" * 12 + "-secretvalue"
PIPELINE = {"steps": [{"agent": "any", "capability": "tag:review", "access": "read", "goal": "g"}]}


class FakeHttp:
    def __init__(self, post_reply=None):
        self.calls = []
        self.post_reply = post_reply or {"ok": True, "ts": "1.2"}

    def __call__(self, method, body, token):
        self.calls.append((method, body))
        return {"ok": True, "bot_id": "B1"} if method == "auth.test" else self.post_reply


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_TOK", TOKEN)
    f = tmp_path / "p.json"
    f.write_text(json.dumps(PIPELINE))
    return f


def argv(*extra):
    return [
        "--token-env",
        "MY_TOK",
        "--channel",
        "<CHANNEL_ID>",
        "--agent",
        "UAGENT",
        "--title",
        "Review MR",
        *extra,
    ]


def test_form_a_payload():
    m = pt.build_trigger_message("C1", "UA", PIPELINE, None, "Review MR", "B1")
    assert m["text"] == "<@UA> Review MR"
    assert "thread_ts" not in m
    p = m["metadata"]["event_payload"]
    assert m["metadata"]["event_type"] == "pipe.task.v1"
    assert p["pipeline"] == PIPELINE and p["by"] == "B1" and p["hop"] == 0
    assert not {"task_id", "next", "source"} & set(p)
    assert "flow:" not in m["text"]


def test_form_b_payload():
    m = pt.build_trigger_message("C1", "UA", None, "nightly", "Check things", "B1")
    assert m["text"] == "<@UA> flow:nightly Check things"
    assert "pipeline" not in m["metadata"]["event_payload"]


def test_both_or_neither_refused():
    with pytest.raises(ValueError):
        pt.build_trigger_message("C1", "UA", PIPELINE, "f", "t", "B1")
    with pytest.raises(ValueError):
        pt.build_trigger_message("C1", "UA", None, None, "t", "B1")
    with pytest.raises(ValueError):
        pt.build_trigger_message("C1", "UA", None, "f", "  ", "B1")


def test_title_scrubbed():
    t = "a\nb <!channel> <@U9> " + TOKEN + " " + "x" * 300
    m = pt.build_trigger_message("C1", "UA", PIPELINE, None, t, "B1")
    body = m["text"][len("<@UA> ") :]
    assert "\n" not in body and "<!channel>" not in body and "<@U9>" not in body
    assert "xoxb" not in body and len(body) <= 200


@pytest.mark.parametrize("val", [None, "", "  "])
def test_bad_token_refused(monkeypatch, val):
    monkeypatch.delenv("MY_TOK", raising=False)
    if val is not None:
        monkeypatch.setenv("MY_TOK", val)
    with pytest.raises(ValueError) as e:
        pt.read_token("MY_TOK")
    assert "MY_TOK" in str(e.value)


def test_main_posts_and_prints_no_secret(env, capsys):
    http = FakeHttp()
    assert pt.main(argv("--pipeline-file", str(env)), http=http) == 0
    out = capsys.readouterr()
    assert not re.search(r"xox|glpat-|Bearer", out.out + out.err) and TOKEN not in out.out + out.err
    method, body = http.calls[-1]
    assert method == "chat.postMessage" and body["channel"] == "<CHANNEL_ID>"
    assert body["metadata"]["event_payload"]["by"] == "B1"


def test_main_refuses_both_forms(env):
    http = FakeHttp()
    assert pt.main(argv("--pipeline-file", str(env), "--flow", "f"), http=http) != 0
    assert http.calls == []


def test_main_missing_token_no_call(monkeypatch, env, capsys):
    monkeypatch.delenv("MY_TOK")
    http = FakeHttp()
    assert pt.main(argv("--flow", "f"), http=http) != 0
    assert http.calls == [] and TOKEN not in capsys.readouterr().err


def test_main_slack_error_name_only(env, capsys):
    http = FakeHttp({"ok": False, "error": "channel_not_found"})
    assert pt.main(argv("--flow", "f"), http=http) != 0
    assert "channel_not_found" in capsys.readouterr().err


def test_bad_pipeline_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MY_TOK", TOKEN)
    f = tmp_path / "bad.json"
    f.write_text("{nope")
    assert pt.main(argv("--pipeline-file", str(f)), http=FakeHttp()) != 0


def test_yml_has_only_placeholders():
    text = (ROOT / "templates/trigger/gitlab-ci.yml").read_text()
    assert not re.search(r"xox|xapp|glpat-|Bearer ", text)
    assert not re.search(r"\b[CUBW][A-Z0-9]{8,}\b", text)
    assert "<CHANNEL_ID>" in text and "<AGENT_USER_ID>" in text


def card_argv(*extra):
    return [
        "card", "--token-env", "MY_TOK", "--agents-channel", "CAG", "--owner", "UOWN",
        "--bot-user-id", "UBOT", "--name", "trigger-bot", *extra,
    ]  # fmt: skip


def test_card_posts_trigger_card(monkeypatch, capsys):
    monkeypatch.setenv("MY_TOK", TOKEN)
    http = FakeHttp()
    assert pt.main(card_argv(), http=http) == 0
    method, msg = http.calls[-1]
    assert method == "chat.postMessage" and msg["channel"] == "CAG"
    assert msg["metadata"]["event_type"] == "pipe.card.v1"
    card = msg["metadata"]["event_payload"]
    assert card["kind"] == "trigger" and card["skills"] == []
    assert card["owner"] == "UOWN" and card["bot_user_id"] == "UBOT"
    out = capsys.readouterr()
    assert TOKEN not in out.out + out.err


def test_card_refuses_invalid(monkeypatch, capsys):
    monkeypatch.setenv("MY_TOK", TOKEN)
    http = FakeHttp()
    bad = card_argv()
    bad[bad.index("--bot-user-id") + 1] = "bad id!"
    assert pt.main(bad, http=http) == 1
    assert not [c for c in http.calls if c[0] == "chat.postMessage"]
    assert TOKEN not in capsys.readouterr().err
