"""Map a core RunRequest to claude load and tool flags (contracts/runtime-request.md)."""

from dataclasses import dataclass

from pipe.core.exposure import state_of
from pipe.runtime_claude_capability import ClaudeCapability
from pipe.runtime_claude_exposure import to_core
from pipe.runtime_claude_loadset import LoadSet, load_set
from pipe.runtime_claude_tools import ToolPolicy, effective_deny_rules, tools_for

WRITE_TOOLS = ["Edit", "Write", "NotebookEdit"]


@dataclass(frozen=True)
class StepTools:
    policy: ToolPolicy
    load: LoadSet


def map_request(request, cfg, caps: list[ClaudeCapability]) -> StepTools:
    """`caps` are the discovered claude capabilities. Raises ValueError for `write`."""
    if request.access != "read":
        raise ValueError("access write is not supported")
    base = tools_for(request.requester_is_owner, cfg.owner_tools, cfg.deny_rules)
    keep = lambda ts: [t for t in ts if t not in WRITE_TOOLS]  # noqa: E731
    deny = effective_deny_rules(cfg.deny_rules) + WRITE_TOOLS
    for c in caps:  # owner-only items are denied by name
        if c.type in ("skill", "command", "mcp") and state_of(to_core(c), cfg.exposed) != "exposed":
            deny.append(f"mcp__{c.name}" if c.type == "mcp" else f"Skill({c.name})")
    deny = list(dict.fromkeys(deny))
    pol = ToolPolicy(keep(base.tools), keep(base.allowed), deny)
    return StepTools(pol, load_set(caps, cfg.exposed, list(request.capabilities)))
