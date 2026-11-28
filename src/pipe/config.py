"""Load and validate ~/.pipe/config.yaml (data-model.md "Agent (config)")."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

from pipe.core.capability import sanitize_tags
from pipe.core.card import _PATH, _URL, _strings
from pipe.core.schema import check_schema
from pipe.core.scrub import scrub
from pipe.runtime_claude_tools import is_broad_bash
from pipe.state import pipe_home

MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\[\]-]*$")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    agent_name: str
    slack_tokens: str
    owner: str = ""
    owner_tools: list[str] = field(default_factory=lambda: ["Read", "Grep", "Glob"])
    repo_roots: list[str] = field(default_factory=list)
    deny_rules: list[str] = field(default_factory=list)
    max_budget_usd: float | None = None
    status_channel: str = "pipe-status"
    model: str | None = None
    step_timeout_min: int = 30
    dialog_timeout_h: int = 24
    warnings: tuple[str, ...] = ()
    exposed: list[str] = field(default_factory=list)
    tags: dict[str, list[str]] = field(default_factory=dict)
    description: str = ""
    agents_channel: str = "pipe-agents"
    capabilities: list[dict] = field(default_factory=list)  # validated declared entries
    write_tools: list[str] = field(
        default_factory=lambda: ["Read", "Grep", "Glob", "Edit", "Write"]
    )
    delegate_repos: dict[str, str] = field(default_factory=dict)  # name -> absolute path
    worktree_root: str = str(Path("~/.pipe/worktrees").expanduser())
    base_branch: str = "main"
    allowlist: list[str] = field(default_factory=list)  # Slack IDs
    work_channel: str = "pipe-work"
    library_marketplaces: list[str] = field(default_factory=list)  # owner-only by default
    mr_state: dict | None = None  # {"gitlab": {"url", "token": "keychain:<service>"}}


def _strs(val, key: str) -> list[str]:
    if not isinstance(val, list) or not all(isinstance(x, str) and x for x in val):
        raise ConfigError(f"{key} must be a list of non-empty strings")
    return val


def _has_token(v) -> bool:
    if isinstance(v, str):
        return v.startswith(("xox", "xapp"))
    if isinstance(v, dict):
        v = list(v.values())
    return isinstance(v, list) and any(_has_token(x) for x in v)


_REPO_NAME = re.compile(r"[A-Za-z0-9._-]{1,64}")
_BRANCH = re.compile(r"[A-Za-z0-9_./][A-Za-z0-9._/-]{0,127}")


def _delegation(rt: dict, roots: list[str]) -> dict:
    """Validate the 004 keys. Errors never quote a name or a path."""
    tools = _strs(
        rt.get("write_tools", Config.__dataclass_fields__["write_tools"].default_factory()),
        "runtime.claude.write_tools",
    )
    if any(r.startswith("Bash") for r in tools):
        raise ConfigError("write_tools: Bash rules are not allowed on write steps")
    repos = rt.get("delegate_repos", {})
    if not isinstance(repos, dict):
        raise ConfigError("runtime.claude.delegate_repos must be a map of name to path")
    real_roots = [os.path.realpath(r) for r in roots]
    out = {}
    for n, p in repos.items():
        if not (isinstance(n, str) and _REPO_NAME.fullmatch(n)):
            raise ConfigError("delegate_repos: a name must match [A-Za-z0-9._-]{1,64}")
        if not (isinstance(p, str) and Path(p).expanduser().is_absolute()):
            raise ConfigError("delegate_repos: each path must be absolute")
        real = os.path.realpath(Path(p).expanduser())
        if not any(real.startswith(r + os.sep) for r in real_roots):
            raise ConfigError("delegate_repos: each path must be inside repo_roots")
        out[n] = str(Path(p).expanduser())
    base = rt.get("base_branch", "main")
    if not (
        isinstance(base, str)
        and _BRANCH.fullmatch(base)
        and ".." not in base
        and not base.endswith((".lock", "/", "."))
    ):
        raise ConfigError("base_branch must be a plain branch name")
    wt = rt.get("worktree_root", "~/.pipe/worktrees")
    if not (isinstance(wt, str) and Path(wt).expanduser().is_absolute()):
        raise ConfigError("worktree_root must be an absolute path")
    return dict(
        write_tools=tools,
        delegate_repos=out,
        base_branch=base,
        worktree_root=str(Path(wt).expanduser()),
    )


_SLACK_ID = r"[BUWA][A-Z0-9]{2,}"
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_COMMON = {"id", "runtime", "name", "description", "access", "tags", "timeout_s"}
_COMMON |= {"input_schema", "output_schema"}
_KEYS = {"exec": _COMMON | {"command", "env_allow"}, "http": _COMMON | {"url", "token"}}
_REQ = {"exec": ("command",), "http": ("url",)}
_ENV = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_LOCAL = ("localhost", "127.0.0.1")


def _tag_list(val, where: str) -> list[str]:
    if not isinstance(val, list) or len(val) > 8 or sanitize_tags(val) != tuple(val):
        raise ConfigError(f"{where}: tags must be a list of at most 8 tags [a-z0-9-], max 32 chars")
    return val


def _cap(e, i: int) -> dict:
    """One declared entry. Errors name the entry, never a command, URL, or token."""
    if not isinstance(e, dict):
        raise ConfigError(f"capabilities[{i}] must be a mapping")
    cid, rt = e.get("id"), e.get("runtime")
    who = f"capability {rt}:{cid}" if isinstance(cid, str) else f"capabilities[{i}]"
    bad = lambda msg: ConfigError(f"{who}: {msg}")  # noqa: E731
    if rt not in _KEYS:
        raise bad("runtime must be exec or http")
    if extra := set(e) - _KEYS[rt]:
        raise bad(f"unknown keys: {sorted(map(str, extra))}")
    for k in ("id", "name", "description", "access", *_REQ[rt]):
        if k not in e:
            raise bad(f"missing key {k}")
    if not (isinstance(cid, str) and _ID.fullmatch(cid)):
        raise bad("bad id")
    if not (isinstance(e["name"], str) and 1 <= len(e["name"]) <= 80):
        raise bad("name must be 1 to 80 characters")
    if not (isinstance(e["description"], str) and len(e["description"]) <= 200):
        raise bad("description must be at most 200 characters")
    if e["access"] != "read":
        raise bad("access must be read")
    t = e.get("timeout_s", 1)
    if isinstance(t, bool) or not isinstance(t, int) or not 1 <= t <= 3600:
        raise bad("timeout_s must be an integer from 1 to 3600")
    _tag_list(e.get("tags", []), who)
    out = dict(e)
    if rt == "exec":
        cmd = e["command"]
        if not (isinstance(cmd, list) and cmd and all(isinstance(x, str) and x for x in cmd)):
            raise bad("command must be a non-empty list of strings")
        if not Path(cmd[0]).expanduser().is_absolute():
            raise bad("command[0] must be an absolute path")
        out["command"] = [str(Path(cmd[0]).expanduser()), *cmd[1:]]
        env = e.get("env_allow", [])
        if not (isinstance(env, list) and all(_ENV.fullmatch(str(x)) for x in env)):
            raise bad("env_allow must be a list of variable names")
    else:
        u = urlparse(e["url"]) if isinstance(e["url"], str) else None
        ok = u and (u.scheme == "https" or (u.scheme == "http" and u.hostname in _LOCAL))
        if not (ok and u.hostname and u.username is None and u.password is None):
            raise bad("url must be https (http only for localhost) with no user name or password")
        tok = e.get("token")
        if tok is not None and not (isinstance(tok, str) and re.fullmatch(r"keychain:\S+", tok)):
            raise bad("token must be keychain:<service>")
    for k in ("input_schema", "output_schema"):
        if k in e:
            if check_schema(e[k]):
                raise bad(f"{k} is not a valid schema")
            for s in _strings(e[k]):
                if _URL.search(s) or _PATH.search(s) or scrub(s) != s:
                    raise bad(f"{k} holds a URL, a path, or a token-like string")
    return out


def _caps(raw, exposed: list[str]) -> list[dict]:
    if not isinstance(raw, list):
        raise ConfigError("capabilities must be a list")
    out = [_cap(e, i) for i, e in enumerate(raw)]
    seen = set()
    for e in out:
        key = f"{e['runtime']}:{e['id']}"
        if key in seen:
            raise ConfigError(f"capability {key} is declared twice")
        seen.add(key)
        if e["runtime"] == "exec" and key in exposed and "input_schema" not in e:
            raise ConfigError(f"capability {key} is exposed and has no input_schema")
    return out


def _mr_state(raw) -> dict | None:
    """Optional GitLab MR state. Errors name the key, never a URL or a token."""
    if raw is None:
        return None
    gl = raw.get("gitlab") if isinstance(raw, dict) else None
    if not (isinstance(gl, dict) and set(gl) == {"url", "token"}):
        raise ConfigError("mr_state must be a map with gitlab: {url, token}")
    u = urlparse(gl["url"]) if isinstance(gl["url"], str) else None
    if not (u and u.scheme == "https" and u.hostname and u.username is None and u.password is None):
        raise ConfigError("mr_state.gitlab.url must be https")
    if not (isinstance(gl["token"], str) and re.fullmatch(r"keychain:\S+", gl["token"])):
        raise ConfigError("mr_state.gitlab.token must be keychain:<service>")
    return {"gitlab": dict(gl)}


def validate_config(raw: dict) -> Config:
    """Pure: raw dict in, Config (with warnings) out. Raises ConfigError."""
    if not isinstance(raw, dict):
        raise ConfigError("config must be a mapping")
    for k in ("owner_tools", "repo_roots"):
        if k in raw:
            raise ConfigError(f"top-level '{k}' is not allowed: use runtime.claude.{k}")
    name = raw.get("agent_name")
    if not isinstance(name, str) or not name:
        raise ConfigError("agent_name is required")
    tokens = raw.get("slack_tokens")
    if not isinstance(tokens, str) or not re.fullmatch(r"keychain:\S+", tokens):
        raise ConfigError("slack_tokens must be keychain:<service>")
    if _has_token(raw):
        raise ConfigError("a plain token in config is not allowed: use keychain:<service>")
    owner = raw.get("owner") or ""
    if not isinstance(owner, str):
        raise ConfigError("owner must be a string")
    runtime = raw.get("runtime") or {}
    if not isinstance(runtime, dict):
        raise ConfigError("runtime must be a mapping")
    rt = runtime.get("claude") or {}
    if not isinstance(rt, dict):
        raise ConfigError("runtime.claude must be a mapping")
    kw: dict = {}
    if "owner_tools" in rt:
        kw["owner_tools"] = _strs(rt["owner_tools"], "runtime.claude.owner_tools")
        if any(is_broad_bash(r) for r in kw["owner_tools"]):
            raise ConfigError("owner_tools: broad Bash rule not allowed; use Bash(<cmd>:*)")
    roots = (
        _strs(rt["repo_roots"], "runtime.claude.repo_roots") if "repo_roots" in rt else ["~/code"]
    )
    if not roots or not all(Path(r).expanduser().is_absolute() for r in roots):
        raise ConfigError("runtime.claude.repo_roots must be a non-empty list of absolute paths")
    kw |= _delegation(rt, [str(Path(r).expanduser()) for r in roots])
    deny = _strs(rt.get("deny_rules", []), "runtime.claude.deny_rules")
    budget = raw.get("max_budget_usd")
    if budget is not None and (
        isinstance(budget, bool) or not isinstance(budget, int | float) or budget <= 0
    ):
        raise ConfigError("max_budget_usd must be a number greater than 0")
    model = raw.get("model")
    if model is not None and not (isinstance(model, str) and MODEL_RE.match(model)):
        raise ConfigError("model has an invalid format")
    timeout = raw.get("step_timeout_min", 30)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        raise ConfigError("step_timeout_min must be an integer >= 1")
    dialog = raw.get("dialog_timeout_h", 24)
    if isinstance(dialog, bool) or not isinstance(dialog, int) or not 1 <= dialog <= 168:
        raise ConfigError("dialog_timeout_h must be an integer from 1 to 168")
    channel = raw.get("status_channel", "pipe-status")
    if not isinstance(channel, str) or not channel:
        raise ConfigError("status_channel must be a non-empty string")
    exposed = _strs(raw.get("exposed", []), "exposed")
    lib = raw.get("library_marketplaces", [])
    if not (
        isinstance(lib, list)
        and all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", x) for x in lib)
    ):
        raise ConfigError("library_marketplaces must be a list of short names")
    tag_map = raw.get("tags", {})
    if not isinstance(tag_map, dict) or not all(isinstance(k, str) and k for k in tag_map):
        raise ConfigError("tags must be a map from a capability ID to a list of tags")
    for k, v in tag_map.items():
        _tag_list(v, f"tags[{k}]")
    desc = raw.get("description", f"Claude Code agent {name}")
    if not isinstance(desc, str) or len(desc) > 200:
        raise ConfigError("description must be a string of at most 200 characters")
    agents = raw.get("agents_channel", "pipe-agents")
    if not isinstance(agents, str) or not agents:
        raise ConfigError("agents_channel must be a non-empty string")
    work = raw.get("work_channel", "pipe-work")
    if not isinstance(work, str) or not work:
        raise ConfigError("work_channel must be a non-empty string")
    mr_state = _mr_state(raw.get("mr_state"))
    allow = raw.get("allowlist", [])
    if not (
        isinstance(allow, list)
        and all(isinstance(x, str) and re.fullmatch(_SLACK_ID, x) for x in allow)
    ):
        raise ConfigError("allowlist must be a list of Slack IDs")
    caps = _caps(raw.get("capabilities", []), exposed)
    warnings = () if owner else ("owner is empty: no sender gets tools",)
    return Config(
        agent_name=name,
        slack_tokens=tokens,
        owner=owner,
        repo_roots=[str(Path(r).expanduser()) for r in roots],
        deny_rules=deny,
        max_budget_usd=budget,
        status_channel=channel,
        model=model,
        step_timeout_min=timeout,
        dialog_timeout_h=dialog,
        warnings=warnings,
        exposed=exposed,
        library_marketplaces=lib,
        tags=tag_map,
        description=desc,
        agents_channel=agents,
        capabilities=caps,
        allowlist=allow,
        work_channel=work,
        mr_state=mr_state,
        **kw,
    )


def load_config(path: Path | None = None) -> Config:
    path = path or pipe_home() / "config.yaml"
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise ConfigError(f"config.yaml not found: {path}") from None
    except yaml.YAMLError as e:
        # Only problem + position: the full text can quote a token line.
        m = getattr(e, "problem_mark", None)
        where = f" (line {m.line + 1}, column {m.column + 1})" if m else ""
        raise ConfigError(
            f"config.yaml is not valid YAML: {getattr(e, 'problem', '')}{where}"
        ) from None
    return validate_config(raw)
