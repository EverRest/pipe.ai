"""`pipe capabilities` (T012, T015, T025, T063): no Slack, no Keychain, names only."""

import json

import yaml

from fakes import FAKE_SECRET, FAKE_URL, build_claude_tree
from pipe import keychain
from pipe.cli import main


def setup(tmp_path, monkeypatch, pipe_home, **extra):
    home, roots = build_claude_tree(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    cfg = {
        "agent_name": "a",
        "slack_tokens": "keychain:x",
        "runtime": {"claude": {"repo_roots": roots}},
        **extra,
    }
    (pipe_home / "config.yaml").write_text(yaml.safe_dump(cfg))
    return home


def test_lists_names_only(tmp_path, monkeypatch, pipe_home, capsys):
    def boom(*a):
        raise AssertionError("keychain used")

    monkeypatch.setattr(keychain, "read_token", boom)
    home = setup(tmp_path, monkeypatch, pipe_home, exposed=["skill:pa:clean", "skill:gone"])
    assert main(["capabilities"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert any(
        ln.startswith("exposed") and "skill:pa:clean" in ln for ln in lines
    )  # listed by owner
    assert any(ln.startswith("owner-only") and "mcp:gl" in ln for ln in lines)
    assert any(ln.startswith("owner-only") and "repo:one" in ln for ln in lines)
    types = [ln.split()[1] for ln in lines if ln.startswith(("exposed", "owner-only"))]
    assert types == sorted(types)
    assert "capabilities:" in out and "NOTICE unknown_id: skill:gone" in out
    for bad in (str(tmp_path), FAKE_URL, FAKE_SECRET, "d clean", "xox"):
        assert bad not in out
    assert json.dumps(str(home)) not in out


def test_declared_capability_listed(tmp_path, monkeypatch, pipe_home, capsys):
    cap = {
        "id": "lint",
        "runtime": "exec",
        "name": "Lint repo",
        "description": "d",
        "access": "read",
        "command": ["/bin/true"],
    }
    setup(tmp_path, monkeypatch, pipe_home, capabilities=[cap])
    assert main(["capabilities"]) == 0
    out = capsys.readouterr().out
    assert "owner-only  exec     exec:lint" in out and "/bin/true" not in out
