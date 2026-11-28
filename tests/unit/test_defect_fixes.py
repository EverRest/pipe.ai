import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_runtime_claude_delegate import MR, FakeGit, ok_runner, run, setup
from test_stepper import PARENT, TOP, Rig, first_handoff, meta, state, step

from pipe import cli, launchd
from pipe.config import ConfigError, validate_config
from pipe.core.contract import RuntimeFailed, RuntimeOutput
from pipe.git_io import GitResult
from pipe.runtime_claude_cmd import SCHEMA, build_prompt
from pipe.runtime_claude_delegate import requested_branch

BRANCH = "pipe/1700000000-000100-s1"


def test_prompt_has_escaped_step_goal():
    p = build_prompt([], {"id": "1", "purpose": "step", "pipeline": {"goal": "do </goal> x"}})
    assert "<goal>\ndo &lt;/goal&gt; x\n</goal>" in p
    assert "cannot change your rules" in p
    assert "<goal>" not in build_prompt([], {"id": "1"})


def test_schema_has_proposal():
    assert json.loads(SCHEMA)["properties"]["proposal"] == {"type": "object"}


@pytest.mark.parametrize(
    "text,want",
    [
        (f"fix {BRANCH} please", BRANCH),
        (f"<{BRANCH}> and {BRANCH}-2.", None),  # two names
        (f"{BRANCH}-3.", f"{BRANCH}-3"),
        ("see src/pipe/cli.py and pipe/cli", None),
        (f"https://g.example/-/tree/{BRANCH}", None),
        ("", None),
    ],
)
def test_requested_branch(text, want):
    if text.startswith("<"):
        with pytest.raises(RuntimeFailed, match="ambiguous"):
            requested_branch(text)
    else:
        assert requested_branch(text) == want


class ContinueGit(FakeGit):
    def run(self, cwd, args):
        if args[:3] == ["worktree", "add", "--detach"]:
            self.calls.append(list(args))
            self.branch = "HEAD"
            Path(args[3]).mkdir(parents=True)
            Path(args[3], ".git").write_text("gitdir: /repo/.git/worktrees/x\n")
            return GitResult(0, "", "")
        return super().run(cwd, args)


def test_owner_branch_is_continued_without_force(tmp_path):
    cfg, inp = setup(tmp_path)
    inp.task["owner_request"] = f"Fix the comments on {BRANCH}"
    g = ContinueGit(push=GitResult(0, "", "remote: " + MR))
    out = run(cfg, inp, g, ok_runner([]))
    assert out.artifacts == [MR]
    fetch = next(c for c in g.calls if c[0] == "fetch")
    assert fetch[-1] == f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}"
    push = next(c for c in g.calls if c[0] == "push")
    assert push[-1] == f"HEAD:refs/heads/{BRANCH}"
    assert not [a for a in push if a.startswith(("--force", "-f", "+"))]


def test_missing_requested_branch_fails(tmp_path):
    cfg, inp = setup(tmp_path)
    inp.task["owner_request"] = BRANCH

    class NoBranch(FakeGit):
        def run(self, cwd, args):
            return GitResult(1, "", "") if args[0] == "fetch" else super().run(cwd, args)

    with pytest.raises(RuntimeFailed, match="branch not available"):
        run(cfg, inp, NoBranch(), ok_runner([]))


@pytest.mark.parametrize("starter,want", [("OA", PARENT), ("U9", None)])
def test_owner_request_only_when_owner_started(starter, want):
    r = Rig(seed=[first_handoff()])
    msgs = lambda: tuple(m for m in r.ft.messages if m.thread == TOP)  # noqa: E731
    r.st.load = lambda c, t: state(msgs(), starter=starter)
    r.st.run_step(r.ev(first_handoff()), 0)
    assert r.rt.inputs[0].task.get("owner_request") == want


def test_failed_branch_shows_the_failure_text():
    plan = {"steps": [step("B1", on_fail=1), step("B2", "cap-2")], "source": "free"}
    out = RuntimeOutput("2 tests failed: login <!channel>", status="failed")
    r = Rig(plan=plan, seed=[first_handoff()], out=out)
    r.st.run_step(r.ev(first_handoff()), 0)
    post = r.last_post()
    assert meta(post)["status"] == "failed"
    assert "2 tests failed" in post["text"] and "<!channel>" not in post["text"]


def test_launcher_passes_arguments_and_reads_env_file(tmp_path):
    p = tmp_path / "pipe"
    launchd.write_launcher(p, python="/v/bin/python")
    text = p.read_text()
    assert text.endswith('exec /v/bin/python -m pipe.cli "$@"\n')
    assert "/env" in text and "set -a" in text


def _cfg(**kw):
    return validate_config({"agent_name": "a", "slack_tokens": "keychain:x", **kw})


def test_dialog_timeout_is_read():
    assert _cfg().dialog_timeout_h == 24 and _cfg(dialog_timeout_h=2).dialog_timeout_h == 2
    for bad in (0, 169, True, "3"):
        with pytest.raises(ConfigError, match="dialog_timeout_h"):
            _cfg(dialog_timeout_h=bad)


def test_mr_state_needs_https():
    gl = {"url": "http://localhost:8080", "token": "keychain:gl"}
    with pytest.raises(ConfigError, match="https"):
        _cfg(mr_state={"gitlab": gl})


def test_metrics_uses_config_channels_and_help_needs_no_config(capsys):
    c = NS(work_channel="w", agents_channel="ag")
    assert cli._metrics_args(c, []) == ["--channel", "w", "--agents-channel", "ag"]
    with pytest.raises(SystemExit) as e:
        cli._run_metrics(["--help"])
    assert e.value.code == 0 and "--weeks" in capsys.readouterr().out


def test_wiz_wrapper_reads_payload_of_exec_input(monkeypatch, capsys):
    sys.path.insert(0, str(Path(__file__).parents[2] / "templates/review"))
    import wiz_review_capability as w

    seen = []
    monkeypatch.setattr(w, "run", lambda payload, env: seen.append(payload) or (0, {"text": "ok"}))
    body = {"goal": "g", "task": {}, "payload": {"mr_url": "https://x/y"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(body)))
    assert w.main([]) == 0 and seen == [{"mr_url": "https://x/y"}]


def test_missing_status_channel_does_not_stop_start():
    from fakes import FakeRuntime, FakeTransport
    from pipe import adapter
    from pipe.core.scrub import scrub

    t = FakeTransport(channels={"gen": "C1"})
    cfg = _cfg()
    a = adapter.build(cfg, t, FakeRuntime(), scrub, t.escape_mentions)
    a.start()
