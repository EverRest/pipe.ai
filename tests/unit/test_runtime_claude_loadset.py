from pipe.runtime_claude_capability import ClaudeCapability
from pipe.runtime_claude_loadset import load_set


def c(type, name, source="", plugin=None, plugin_id=None, **kw):
    pid = f"{type}:{plugin}:{name}" if plugin else f"{type}:{name}"
    return ClaudeCapability(
        id=pid, type=type, name=name, source=source, plugin=plugin, plugin_id=plugin_id, **kw
    )


OPEN = dict(allowed_tools=("Read",))
CAPS = [
    c("skill", "open", "/s/open", **OPEN),
    c("skill", "closed", "/s/closed"),
    c("command", "cmd", "/c/cmd.md", **OPEN),
    c("mcp", "gl"),
    c("plugin", "p"),
    c("skill", "ps", "/p/skills/ps", plugin="p", plugin_id="plugin:p"),
    c("repo", "r"),
]
ALL = [x.id for x in CAPS]


def test_open_and_sorted():
    s = load_set(CAPS, [], ALL)
    assert [n for n, _ in s.skills] == ["open"] and s.skills[0][1] == "/s/open"
    assert s.commands == (("cmd", "/c/cmd.md"),) and s.mcp == ()
    kinds = {n.id for n in s.skipped}
    assert {"skill:closed", "mcp:gl", "plugin:p", "repo:r", "skill:p:ps"} <= kinds


def test_owner_listed_and_plugin_group():
    s = load_set(CAPS, ["skill:closed", "mcp:gl", "plugin:p", "repo:r"], ALL)
    assert [n for n, _ in s.skills] == ["closed", "open", "ps"]
    assert s.mcp == ("gl",)
    assert set(s.allowed_rules) == {
        "Skill(pipe-exposed:closed)", "Skill(pipe-exposed:open)", "Skill(pipe-exposed:ps)",
        "Skill(pipe-exposed:cmd)", "mcp__gl",
    }  # fmt: skip
    assert s.needs_skill_tool


def test_ids_filter_and_empty():
    s = load_set(CAPS, ["skill:closed"], ["skill:open", "skill:nope", "skill:closed"])
    assert [n for n, _ in s.skills] == ["closed", "open"]
    assert [n.id for n in s.skipped] == ["skill:nope"]
    e = load_set(CAPS, [], [])
    assert e.skills == e.commands == e.mcp == e.skipped == () and not e.needs_skill_tool
    assert not load_set(CAPS, [], ["skill:closed"]).needs_skill_tool


def test_link_name_collision():
    a = c("skill", "x", "/a/same", plugin="p1", **OPEN)
    b = c("skill", "x", "/b/same", plugin="p2", **OPEN)
    s = load_set([a, b], [], [a.id, b.id])
    assert s.skills == (("same", "/a/same"),) and [n.id for n in s.skipped] == [b.id]
