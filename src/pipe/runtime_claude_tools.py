"""Tool policy of the claude adapter (FR-016, FR-019). Not a core module."""

from dataclasses import dataclass

PUSH_DENY = "Bash(git push:*)"


@dataclass(frozen=True)
class ToolPolicy:
    tools: list[str]
    allowed: list[str]
    disallowed: list[str]
    restricted: bool = True


def effective_deny_rules(deny_rules: list[str] | None) -> list[str]:
    """Default rule first, then the owner's rules. The owner cannot remove the default."""
    return [PUSH_DENY] + [r for r in (deny_rules or []) if r != PUSH_DENY]


def tools_for(
    requester_is_owner: bool, owner_tools: list[str], deny_rules: list[str] | None
) -> ToolPolicy:
    if not requester_is_owner:
        return ToolPolicy([], [], [])
    return ToolPolicy(list(owner_tools), list(owner_tools), effective_deny_rules(deny_rules))
