import json
import subprocess
from pathlib import Path

import pytest

from pipe.config import Config
from pipe.core.contract import RuntimeFailed, RuntimeInput
from pipe.runtime_claude import ClaudeRuntime, build_cmd, build_prompt
from pipe.runtime_claude_tools import effective_deny_rules, tools_for

CFG = Config(agent_name="a", slack_tokens="keychain:x", repo_roots=["/r1", "/r2"])
INP = dict(thread=[{"user": "bob", "text": "hi"}], task={"id": "t1", "purpose": "chat"})
OK = json.dumps({"result": json.dumps({"text": "hello", "status": "done"})})


class Fake:
    def __init__(self, out=OK, code=0, exc=None):
        self.out, self.code, self.exc, self.calls = out, code, exc, []

    def __call__(self, argv, stdin, env, cwd, timeout):
        self.calls.append(dict(argv=argv, stdin=stdin, env=env, cwd=cwd, timeout=timeout))
        if self.exc:
            raise self.exc
        return self.code, self.out


def rt(fake, cfg=CFG, **kw):
    return ClaudeRuntime(cfg, runner=fake, scrub=lambda s: s.replace("SECRET", "[redacted]"), **kw)


def val(argv, flag):
    return argv[argv.index(flag) + 1]


def test_non_owner_cmd():
    cmd = build_cmd(CFG, tools_for(False, CFG.owner_tools, []))
    assert cmd[:2] == ["claude", "-p"]
    assert val(cmd, "--tools") == ""
    assert "--restricted" in cmd and val(cmd, "--permission-mode") == "dontAsk"
    for f in ("--allowedTools", "--add-dir", "--disallowedTools", "--model", "--max-budget-usd"):
        assert f not in cmd


def test_owner_cmd():
    cfg = Config(
        **{**CFG.__dict__, "model": "opus", "max_budget_usd": 1.5, "deny_rules": ["Bash(rm:*)"]}
    )
    cmd = build_cmd(cfg, tools_for(True, cfg.owner_tools, cfg.deny_rules))
    assert val(cmd, "--tools") == "Read,Grep,Glob"
    i = cmd.index("--allowedTools")
    assert cmd[i + 1 : i + 7] == [
        "Read(//r1/**)", "Grep(//r1/**)", "Glob(//r1/**)",
        "Read(//r2/**)", "Grep(//r2/**)", "Glob(//r2/**)",
    ]  # fmt: skip
    assert cmd.count("--add-dir") == 1 and val(cmd, "--add-dir") == "/r2"
    j = cmd.index("--disallowedTools")
    assert cmd[j + 1 : j + 9] == [*effective_deny_rules([]), "Bash(rm:*)"]
    assert val(cmd, "--model") == "opus" and val(cmd, "--max-budget-usd") == "1.5"
    assert "--restricted" in cmd and "--strict-mcp-config" in cmd


def test_widened_tool_is_bare_allow():
    cfg = Config(**{**CFG.__dict__, "owner_tools": ["Read", "WebFetch"]})
    cmd = build_cmd(cfg, tools_for(True, cfg.owner_tools, []))
    assert "WebFetch" in cmd[cmd.index("--allowedTools") + 1 :]
    assert "Read(//r1/**)" in cmd and "WebFetch(//r1/**)" not in cmd


def test_tilde_expanded():
    cfg = Config(**{**CFG.__dict__, "repo_roots": ["~/code"]})
    cmd = build_cmd(cfg, tools_for(True, cfg.owner_tools, []))
    assert f"Read(/{Path('~/code').expanduser()}/**)" in cmd


def test_run_ok_and_env(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-1")
    monkeypatch.setenv("HOME", "/home/x")
    f = Fake()
    out = rt(f).run(RuntimeInput(requester_is_owner=False, **INP))
    assert out.text == "hello" and out.status == "done"
    c = f.calls[0]
    assert c["env"]["PIPE_RUNTIME"] == "1" and "SLACK_BOT_TOKEN" not in c["env"]
    assert c["cwd"] == "/r1" and c["timeout"] == 30 * 60
    assert "--tools" in c["argv"] and "hi" in c["stdin"]


def test_structured_output_envelope():
    env = json.dumps({"structured_output": {"text": "x", "status": "done"}})
    assert rt(Fake(out=env)).run(RuntimeInput(requester_is_owner=True, **INP)).text == "x"


def test_output_scrubbed_and_escaped():
    body = json.dumps(
        {"text": "SECRET <!here>", "status": "failed", "reason": "SECRET", "artifacts": ["SECRET"]}
    )
    f = Fake(out=json.dumps({"result": body}))
    out = ClaudeRuntime(
        CFG,
        runner=f,
        scrub=lambda s: s.replace("SECRET", "[redacted]"),
        escape_mentions=lambda s: s.replace("<!here>", "here"),
    ).run(RuntimeInput(requester_is_owner=True, **INP))
    assert (
        out.text == "[redacted] here"
        and out.reason == "[redacted]"
        and out.artifacts == ["[redacted]"]
    )


@pytest.mark.parametrize(
    "fake,reason",
    [
        (Fake(exc=subprocess.TimeoutExpired("claude", 1)), "timeout"),
        (Fake(exc=FileNotFoundError()), "command not found"),
        (Fake(code=2), "exit 2"),
        (Fake(out="not json"), "invalid"),
        (Fake(out=json.dumps({"result": "nope"})), "not valid JSON"),
    ],
)
def test_failures(fake, reason):
    with pytest.raises(RuntimeFailed, match=reason):
        rt(fake).run(RuntimeInput(requester_is_owner=True, **INP))


def test_prompt_untrusted_no_trust_data():
    p = build_prompt(INP["thread"], {"id": "t1", "purpose": "chat", "hop": 3})
    assert "untrusted" in p.lower() and "bob" in p and "hop" not in p.lower()


def _prep(plugin=True, mcp=True):
    from pipe.runtime_claude_load import PreparedLoad

    return PreparedLoad(
        Path("/run/x/exposed-plugin") if plugin else None,
        Path("/run/x/mcp.json") if mcp else None,
        ["Skill"] if plugin else [],
        (["Skill(pipe-exposed:s)"] if plugin else []) + (["mcp__gl"] if mcp else []),
    )


def test_build_cmd_prepared_none_is_001():
    pol = tools_for(True, ["Read"], [])
    assert build_cmd(CFG, pol, None) == build_cmd(CFG, pol)
    assert "--plugin-dir" not in build_cmd(CFG, pol) and "--mcp-config" not in build_cmd(CFG, pol)


def test_build_cmd_prepared_flags():
    pol = tools_for(True, ["Read"], [])
    cmd = build_cmd(CFG, pol, _prep())
    assert val(cmd, "--plugin-dir") == "/run/x/exposed-plugin"
    assert val(cmd, "--mcp-config") == "/run/x/mcp.json"
    assert "--strict-mcp-config" in cmd and "--restricted" in cmd
    assert val(cmd, "--permission-mode") == "dontAsk"
    assert val(cmd, "--tools") == "Read,Skill"
    rules = cmd[cmd.index("--allowedTools") + 1 :]
    assert "Skill(pipe-exposed:s)" in rules and "mcp__gl" in rules and "Read(//r1/**)" in rules


def test_build_cmd_prepared_non_owner_and_partial():
    pol = tools_for(False, [], [])
    cmd = build_cmd(CFG, pol, _prep(plugin=False))
    assert val(cmd, "--tools") == "" and "--plugin-dir" not in cmd
    assert val(cmd, "--allowedTools") == "mcp__gl"
    cmd = build_cmd(CFG, pol, _prep(mcp=False))
    assert val(cmd, "--tools") == "Skill" and "--mcp-config" not in cmd


def test_build_cmd_empty_prepared_adds_nothing():
    from pipe.runtime_claude_load import PreparedLoad

    pol = tools_for(True, ["Read"], [])
    assert build_cmd(CFG, pol, PreparedLoad(None, None, [], [])) == build_cmd(CFG, pol)


def _req(access):
    from pipe.core.runrequest import RunRequest

    return RunRequest(("c",), access, True)


def _rt_write(monkeypatch, req):
    calls = []

    def fake_write(inp, cfg, git, runner, caps, *a):
        calls.append((git, runner))
        return "W"

    monkeypatch.setattr("pipe.runtime_claude.run_write", fake_write)
    fake, git = Fake(), object()
    inp = RuntimeInput(**INP, requester_is_owner=True, request=req)
    return rt(fake, git=git), inp, calls, fake, git


def test_write_run_calls_run_write(monkeypatch):
    r, inp, calls, fake, git = _rt_write(monkeypatch, _req("write"))
    assert r.run(inp) == "W"
    assert calls == [(git, fake)]
    assert fake.calls == []


def test_read_run_skips_run_write(monkeypatch):
    r, inp, calls, fake, _ = _rt_write(monkeypatch, None)
    assert r.run(inp).text == "hello"
    assert calls == [] and fake.calls
