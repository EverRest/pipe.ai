"""Load and validate ~/.pipe/config.yaml (data-model.md "Agent (config)")."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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
    warnings: tuple[str, ...] = ()


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
    roots = (
        _strs(rt["repo_roots"], "runtime.claude.repo_roots") if "repo_roots" in rt else ["~/code"]
    )
    if not roots or not all(Path(r).expanduser().is_absolute() for r in roots):
        raise ConfigError("runtime.claude.repo_roots must be a non-empty list of absolute paths")
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
    channel = raw.get("status_channel", "pipe-status")
    if not isinstance(channel, str) or not channel:
        raise ConfigError("status_channel must be a non-empty string")
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
        warnings=warnings,
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
