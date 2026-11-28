"""Map a core RunRequest to claude load and tool flags (contracts/runtime-request.md)."""

from dataclasses import dataclass

from pipe.core.exposure import state_of
from pipe.runtime_claude_capability import ClaudeCapability
from pipe.runtime_claude_exposure import to_core
from pipe.runtime_claude_loadset import LoadSet, load_set
from pipe.runtime_claude_tools import ToolPolicy, effective_deny_rules, tools_for

WRITE_TOOLS = ["Edit", "Write", "NotebookEdit"]
DEFAULT_WRITE_TOOLS = ["Read", "Grep", "Glob", "Edit", "Write"]


@dataclass(frozen=True)
class StepTools:
    policy: ToolPolicy
    load: LoadSet


def _library(cfg) -> list[str]:
    return getattr(cfg, "library_marketplaces", [])


def _owner_only_deny(cfg, caps) -> list[str]:
    deny = []
    for c in caps:  # owner-only items are denied by name
        core = to_core(c, _library(cfg))
        if c.type in ("skill", "command", "mcp") and state_of(core, cfg.exposed) != "exposed":
            deny.append(f"mcp__{c.name}" if c.type == "mcp" else f"Skill({c.name})")
    return deny


def map_request(
    request, cfg, caps: list[ClaudeCapability], workdir: str | None = None
) -> StepTools:
    """`caps` are the discovered claude capabilities. `write` needs the worktree `workdir`."""
    if request.access == "write":
        if not workdir:
            raise ValueError("access write needs a worktree")
        tools = list(getattr(cfg, "write_tools", None) or DEFAULT_WRITE_TOOLS)
        # path tools only inside the worktree; scoped Bash(<cmd>:*) as given
        allowed = [t if t.startswith("Bash(") else f"{t}(/{workdir}/**)" for t in tools]
        deny = effective_deny_rules(cfg.deny_rules) + _owner_only_deny(cfg, caps)
        pol = ToolPolicy(tools, allowed, list(dict.fromkeys(deny)))
        return StepTools(
            pol, load_set(caps, cfg.exposed, list(request.capabilities), _library(cfg))
        )
    if request.access != "read":
        raise ValueError(f"access {request.access} is not supported")
    base = tools_for(request.requester_is_owner, cfg.owner_tools, cfg.deny_rules)
    keep = lambda ts: [t for t in ts if t not in WRITE_TOOLS]  # noqa: E731
    deny = effective_deny_rules(cfg.deny_rules) + WRITE_TOOLS + _owner_only_deny(cfg, caps)
    deny = list(dict.fromkeys(deny))
    pol = ToolPolicy(keep(base.tools), keep(base.allowed), deny)
    return StepTools(pol, load_set(caps, cfg.exposed, list(request.capabilities), _library(cfg)))
