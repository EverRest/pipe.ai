"""Pure load set for a restricted child (contracts/runtime-load.md, FR-024)."""

from dataclasses import dataclass
from pathlib import Path

from pipe.core.capability import Notice
from pipe.core.exposure import state_of
from pipe.runtime_claude_capability import ClaudeCapability
from pipe.runtime_claude_exposure import to_core

PLUGIN = "pipe-exposed"


@dataclass(frozen=True)
class LoadSet:
    skills: tuple[tuple[str, str], ...] = ()  # (link_name, source_dir)
    commands: tuple[tuple[str, str], ...] = ()  # (link_name, source_file)
    mcp: tuple[str, ...] = ()
    skipped: tuple[Notice, ...] = ()

    @property
    def allowed_rules(self) -> list[str]:
        links = [n for n, _ in self.skills + self.commands]
        return [f"Skill({PLUGIN}:{n})" for n in links] + [f"mcp__{s}" for s in self.mcp]

    @property
    def needs_skill_tool(self) -> bool:
        return bool(self.skills or self.commands)


def load_set(
    caps: list[ClaudeCapability], exposed: list[str], capability_ids: list[str]
) -> LoadSet:
    by_id = {c.id: c for c in caps}
    skills, commands, mcp, skipped, links = [], [], [], [], set()

    def skip(i, why):
        skipped.append(Notice("skipped", i, f"{i} not loaded: {why}"))

    for i in sorted(set(capability_ids)):
        c = by_id.get(i)
        if c is None:
            skip(i, "not found")
        elif (
            c.type not in ("skill", "command", "mcp") or state_of(to_core(c), exposed) != "exposed"
        ):
            skip(i, "not exposed")
        elif c.type == "mcp":
            mcp.append(c.name)
        else:
            link = Path(c.source).stem if c.type == "command" else Path(c.source).name
            if link in links:
                skip(i, "name collision")
                continue
            links.add(link)
            (skills if c.type == "skill" else commands).append((link, c.source))
    return LoadSet(tuple(skills), tuple(commands), tuple(mcp), tuple(skipped))
