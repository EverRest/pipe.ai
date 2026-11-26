"""Tool policy of the claude adapter (FR-016, FR-019). Not a core module."""

from dataclasses import dataclass

# A deny list is best effort, not a security guarantee. The real guard for push
# belongs to spec 004 (worktree, GIT_CONFIG_*).
PUSH_DENY = "Bash(git push:*)"
DEFAULT_DENY = [
    PUSH_DENY,
    *(f"Bash({c}:*)" for c in ("git -C", "git -c", "env", "sh", "bash", "zsh")),
]


def is_broad_bash(rule: str) -> bool:
    """`Bash`, `Bash()`, `Bash(*)`, `Bash(:*)` allow every command."""
    return rule == "Bash" or (
        rule.startswith("Bash(") and rule.endswith(")") and rule[5:-1].strip() in ("", "*", ":*")
    )


@dataclass(frozen=True)
class ToolPolicy:
    tools: list[str]
    allowed: list[str]
    disallowed: list[str]
    restricted: bool = True


def effective_deny_rules(deny_rules: list[str] | None) -> list[str]:
    """Default rules first, then the owner's rules. The owner cannot remove the defaults."""
    return DEFAULT_DENY + [r for r in (deny_rules or []) if r not in DEFAULT_DENY]


def tools_for(
    requester_is_owner: bool, owner_tools: list[str], deny_rules: list[str] | None
) -> ToolPolicy:
    if not requester_is_owner:
        return ToolPolicy([], [], [])
    return ToolPolicy(list(owner_tools), list(owner_tools), effective_deny_rules(deny_rules))
