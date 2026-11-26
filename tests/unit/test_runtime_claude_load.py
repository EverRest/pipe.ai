import json
import logging
import os
import stat

from pipe.runtime_claude_load import PreparedLoad, cleanup, prepare
from pipe.runtime_claude_loadset import LoadSet

FAKE_URL = "https://secret.example/x?token=abc123"


def test_prepare_all(tmp_path, caplog):
    sk = tmp_path / "src" / "myskill"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("x")
    cm = tmp_path / "src" / "cmd.md"
    cm.write_text("cmd body")
    ls = LoadSet(
        skills=(("myskill", str(sk)),), commands=(("cmd", str(cm)),), mcp=("gl", "gone"), skipped=()
    )
    rd = tmp_path / "run" / "r1"
    with caplog.at_level(logging.DEBUG):
        p = prepare(ls, rd, {"gl": {"url": FAKE_URL}})
    pd = rd / "exposed-plugin"
    assert p.plugin_dir == pd
    assert json.loads((pd / ".claude-plugin" / "plugin.json").read_text())["name"] == "pipe-exposed"
    assert (pd / "skills" / "myskill").is_symlink()
    assert os.readlink(pd / "skills" / "myskill") == str(sk)
    assert (pd / "commands" / "cmd.md").read_text() == "cmd body"
    assert not (pd / "commands" / "cmd.md").is_symlink()
    assert p.mcp_file == rd / "mcp.json"
    assert json.loads(p.mcp_file.read_text()) == {"mcpServers": {"gl": {"url": FAKE_URL}}}
    assert stat.S_IMODE(p.mcp_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(rd.stat().st_mode) == 0o700
    assert p.tools == ["Skill"]
    assert p.allowed == ["Skill(pipe-exposed:myskill)", "Skill(pipe-exposed:cmd)", "mcp__gl"]
    assert "gone" in caplog.text and "secret.example" not in caplog.text
    cleanup(rd)
    assert not rd.exists()
    cleanup(rd)  # safe twice


def test_prepare_empty_parts(tmp_path):
    p = prepare(LoadSet((), (), ("gl",), ()), tmp_path / "r", {"gl": {}})
    assert p.plugin_dir is None and p.mcp_file is not None and p.tools == []
    p = prepare(LoadSet((("s", str(tmp_path)),), (), (), ()), tmp_path / "r2", {})
    assert p.mcp_file is None and p.plugin_dir is not None
    assert PreparedLoad(None, None, [], []).tools == []
