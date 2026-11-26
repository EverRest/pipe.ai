from pathlib import Path

import pytest
import yaml

from pipe.config import ConfigError, load_config, validate_config

BASE = {"agent_name": "a1", "slack_tokens": "keychain:pipe-a1", "owner": "U1"}


def cfg(**kw):
    return validate_config({**BASE, **kw})


def test_defaults():
    c = cfg()
    assert c.owner_tools == ["Read", "Grep", "Glob"]
    assert c.repo_roots == [str(Path("~/code").expanduser())]
    assert c.deny_rules == []
    assert c.max_budget_usd is None
    assert c.status_channel == "pipe-status"
    assert c.model is None
    assert c.step_timeout_min == 30
    assert c.warnings == ()


def test_agent_name_required():
    with pytest.raises(ConfigError, match="agent_name"):
        validate_config({k: v for k, v in BASE.items() if k != "agent_name"})


@pytest.mark.parametrize("tok", ["xoxb-1", "xapp-1", "plain", "keychain:"])
def test_bad_slack_tokens(tok):
    with pytest.raises(ConfigError, match="slack_tokens"):
        cfg(slack_tokens=tok)


def test_empty_owner_warns():
    c = validate_config({k: v for k, v in BASE.items() if k != "owner"})
    assert c.owner == "" and any("owner" in w for w in c.warnings)


def test_owner_tools():
    assert cfg(runtime={"claude": {"owner_tools": ["Read", "Edit"]}}).owner_tools == [
        "Read",
        "Edit",
    ]
    for bad in ("Read", [""], [1]):
        with pytest.raises(ConfigError, match="owner_tools"):
            cfg(runtime={"claude": {"owner_tools": bad}})


@pytest.mark.parametrize("v", [0, -1, "x"])
def test_max_budget_rejected(v):
    with pytest.raises(ConfigError, match="max_budget_usd"):
        cfg(max_budget_usd=v)


def test_max_budget_ok():
    assert cfg(max_budget_usd=2.5).max_budget_usd == 2.5


def test_repo_roots():
    assert cfg(runtime={"claude": {"repo_roots": ["~/x"]}}).repo_roots == [
        str(Path("~/x").expanduser())
    ]
    with pytest.raises(ConfigError, match="repo_roots"):
        cfg(runtime={"claude": {"repo_roots": "~/x"}})


def test_deny_rules():
    assert cfg(runtime={"claude": {"deny_rules": ["Bash(rm:*)"]}}).deny_rules == ["Bash(rm:*)"]
    for bad in ("x", [""], [3]):
        with pytest.raises(ConfigError, match="deny_rules"):
            cfg(runtime={"claude": {"deny_rules": bad}})


@pytest.mark.parametrize("key", ["owner_tools", "repo_roots"])
def test_old_top_level_keys(key):
    with pytest.raises(ConfigError, match=f"runtime.claude.{key}"):
        cfg(**{key: ["x"]})


def test_other_runtime_keys_ignored():
    cfg(runtime={"name": "claude", "claude": {}}, allowlist=["U2"], exposed=[])


@pytest.mark.parametrize("m", ["opus", "claude-opus-4.5", "sonnet[1m]"])
def test_model_ok(m):
    assert cfg(model=m).model == m


@pytest.mark.parametrize("m", ["-x", "a b", "", 5])
def test_model_bad(m):
    with pytest.raises(ConfigError, match="model"):
        cfg(model=m)


def test_step_timeout():
    assert cfg(step_timeout_min=1).step_timeout_min == 1
    for bad in (0, "5", True):
        with pytest.raises(ConfigError, match="step_timeout_min"):
            cfg(step_timeout_min=bad)


def test_load_config(pipe_home):
    (pipe_home / "config.yaml").write_text(yaml.safe_dump(BASE))
    assert load_config().agent_name == "a1"


def test_load_config_missing(pipe_home):
    with pytest.raises(ConfigError, match="config.yaml"):
        load_config()


@pytest.mark.parametrize("tok", ["xoxb-1", "xapp-1", "xoxp-1"])
@pytest.mark.parametrize(
    "extra",
    [
        {"description": "TOK"},
        {"runtime": {"claude": {"deny_rules": ["TOK"]}}},
        {"capabilities": [{"name": "c", "key": "TOK"}]},
    ],
)
def test_plain_token_in_any_key(tok, extra):
    import json

    extra = json.loads(json.dumps(extra).replace("TOK", tok))
    with pytest.raises(ConfigError, match="plain token"):
        cfg(**extra)


def test_yaml_error_does_not_leak_text(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: [xoxb-SECRET\nb: : :\n")
    with pytest.raises(ConfigError) as e:
        load_config(p)
    assert "xoxb-SECRET" not in str(e.value) and "line" in str(e.value)


@pytest.mark.parametrize("rt", [["x"], "claude", {"claude": "repo_roots"}, {"claude": ["x"]}])
def test_runtime_wrong_type(rt):
    with pytest.raises(ConfigError, match="runtime"):
        cfg(runtime=rt)


@pytest.mark.parametrize("roots", [[], ["rel/path"], ["code"]])
def test_repo_roots_non_empty_absolute(roots):
    with pytest.raises(ConfigError, match="repo_roots"):
        cfg(runtime={"claude": {"repo_roots": roots}})
