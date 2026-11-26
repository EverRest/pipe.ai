# ruff: noqa: S105, S106, S604  (fake secrets and a fake `shell` key on purpose)
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


@pytest.mark.parametrize("rule", ["Bash", "Bash(*)", "Bash(:*)", "Bash()"])
def test_owner_tools_broad_bash(rule):
    with pytest.raises(ConfigError, match="broad Bash rule not allowed; use Bash"):
        cfg(runtime={"claude": {"owner_tools": ["Read", rule]}})


def test_owner_tools_scoped_bash():
    assert cfg(runtime={"claude": {"owner_tools": ["Bash(ls:*)"]}}).owner_tools == ["Bash(ls:*)"]


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
    cfg(runtime={"name": "claude", "claude": {}}, allowlist=["U2"])


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


# --- stage 002: exposure keys (T005) ---


def test_exposure_defaults():
    c = cfg()
    assert (c.exposed, c.tags, c.capabilities, c.agents_channel) == ([], {}, [], "pipe-agents")
    assert c.description == "Claude Code agent a1"


def test_exposure_ok():
    c = cfg(
        exposed=["skill:a"],
        tags={"skill:a": [], "x": ["a-1"]},
        description="d",
        agents_channel="ag",
    )
    assert c.exposed == ["skill:a"] and c.tags["skill:a"] == [] and c.description == "d"
    assert c.agents_channel == "ag"


@pytest.mark.parametrize(
    "kw",
    [
        {"exposed": "skill:a"},
        {"exposed": [""]},
        {"exposed": [1]},
        {"tags": ["a"]},
        {"tags": {"": ["a"]}},
        {"tags": {"a": "x"}},
        {"tags": {"a": ["Up"]}},
        {"tags": {"a": ["x" * 33]}},
        {"tags": {"a": [f"t{i}" for i in range(9)]}},
        {"description": "x" * 201},
        {"description": 1},
        {"agents_channel": ""},
        {"agents_channel": 3},
    ],
)
def test_exposure_bad(kw):
    with pytest.raises(ConfigError):
        cfg(**kw)


# --- stage 002: declared capabilities (T056, T064) ---

EXEC = {
    "id": "lint-repo",
    "runtime": "exec",
    "name": "Lint",
    "description": "Lint a repo",
    "access": "read",
    "command": ["/usr/bin/true", "--x"],
    "env_allow": ["HOME"],
}
HTTP = {
    "id": "deploys",
    "runtime": "http",
    "name": "Deploys",
    "description": "List deploys",
    "access": "read",
    "url": "https://api.example.com/d",
    "token": "keychain:svc",
    "timeout_s": 10,
}
SCHEMA = {"type": "object", "properties": {"repo": {"type": "string"}}}


def test_capabilities_ok():
    c = cfg(capabilities=[EXEC, HTTP])
    assert [e["id"] for e in c.capabilities] == ["lint-repo", "deploys"]


def test_capabilities_localhost_http_ok():
    cfg(capabilities=[{**HTTP, "url": "http://localhost:8080/x"}])
    cfg(capabilities=[{**HTTP, "url": "http://127.0.0.1/x"}])


def bad(entry, **drop):
    e = {**entry, **{k: v for k, v in drop.items() if v is not None}}
    for k, v in drop.items():
        if v is None:
            e.pop(k)
    return e


SECRET = "/opt/secret-bin"


@pytest.mark.parametrize(
    "entry",
    [
        bad(EXEC, runtime=None),
        bad(EXEC, runtime="shell"),
        bad(EXEC, shell="x"),
        bad(EXEC, env={"A": "b"}),
        bad(EXEC, name=None),
        bad(EXEC, description=None),
        bad(EXEC, access=None),
        bad(EXEC, command=None),
        bad(EXEC, id="Bad Id"),
        bad(EXEC, access="write"),
        bad(EXEC, command="/opt/secret-bin"),
        bad(EXEC, command=["/opt/secret-bin", 1]),
        bad(EXEC, command=[]),
        bad(EXEC, command=["rel/secret-bin"]),
        bad(EXEC, env_allow=["A=B"]),
        bad(EXEC, url="https://x.example"),
        bad(EXEC, timeout_s=0),
        bad(EXEC, timeout_s=3601),
        bad(EXEC, tags=["Bad"]),
        bad(EXEC, input_schema={"$ref": "x"}),
        bad(EXEC, input_schema={"type": "string", "description": "see https://a.example/x"}),
        bad(EXEC, input_schema={"type": "string", "description": "/etc/passwd"}),
        bad(EXEC, input_schema={"type": "string", "description": "xoxb-1234567890-abcdef"}),
        bad(HTTP, command=["/bin/x"]),
        bad(HTTP, url=None),
        bad(HTTP, url="http://evil.example/x"),
        bad(HTTP, url="https://user:pw@api.example.com/d"),
        bad(HTTP, token="ghp_abc"),
        bad(HTTP, token="xoxb-1"),
    ],
)
def test_capabilities_bad(entry):
    with pytest.raises(ConfigError, match=r"lint-repo|deploys|Bad Id|plain token") as e:
        cfg(capabilities=[entry])
    text = str(e.value)
    for leak in (SECRET, "api.example.com", "ghp_abc", "keychain:svc", "evil.example"):
        assert leak not in text


def test_capabilities_wrong_type_and_duplicate():
    with pytest.raises(ConfigError):
        cfg(capabilities={"a": 1})
    with pytest.raises(ConfigError, match="exec:lint-repo"):
        cfg(capabilities=[EXEC, EXEC])
    cfg(capabilities=[EXEC, {**HTTP, "id": "lint-repo"}])  # other runtime: no clash


def test_exposed_exec_needs_input_schema():
    with pytest.raises(
        ConfigError, match=r"capability exec:lint-repo is exposed and has no input_schema"
    ) as e:
        cfg(capabilities=[EXEC], exposed=["exec:lint-repo"])
    assert "/usr/bin/true" not in str(e.value)
    cfg(capabilities=[{**EXEC, "input_schema": SCHEMA}], exposed=["exec:lint-repo"])
    cfg(capabilities=[EXEC], exposed=[])
    cfg(capabilities=[HTTP], exposed=["http:deploys"])
    cfg(exposed=["exec:nope"])
