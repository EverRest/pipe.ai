from types import SimpleNamespace as NS

import pytest

from pipe.runtime_claude_capability import ClaudeCapability
from pipe.runtime_claude_request import map_request
from pipe.runtime_claude_tools import PUSH_DENY

OPEN = dict(allowed_tools=("Read",))
CAPS = [
    ClaudeCapability("skill:open", "skill", "open", source="/s/open", **OPEN),
    ClaudeCapability("skill:closed", "skill", "closed", source="/s/closed"),
    ClaudeCapability("command:cmd", "command", "cmd", source="/c/cmd.md"),
    ClaudeCapability("mcp:gl", "mcp", "gl"),
]


def cfg(**kw):
    d = dict(owner_tools=["Read", "Grep", "Glob"], deny_rules=[], exposed=[])
    return NS(**{**d, **kw})


def req(caps=("skill:open",), access="read", owner=True):
    return NS(capabilities=caps, access=access, requester_is_owner=owner)


def test_owner_read():
    m = map_request(req(), cfg(), CAPS)
    assert m.policy.tools == ["Read", "Grep", "Glob"] and m.policy.restricted
    assert m.policy.allowed == ["Read", "Grep", "Glob"]
    assert [n for n, _ in m.load.skills] == ["open"]
    assert PUSH_DENY in m.policy.disallowed


def test_non_owner_no_tools_but_load_and_deny():
    m = map_request(req(owner=False), cfg(), CAPS)
    assert m.policy.tools == [] and m.policy.allowed == [] and m.policy.restricted
    assert [n for n, _ in m.load.skills] == ["open"]
    assert PUSH_DENY in m.policy.disallowed


def test_read_strips_write_tools_even_if_widened():
    c = cfg(owner_tools=["Read", "Edit", "Write", "NotebookEdit", "Grep"])
    m = map_request(req(), c, CAPS)
    assert m.policy.tools == ["Read", "Grep"] and m.policy.allowed == ["Read", "Grep"]
    assert {"Edit", "Write", "NotebookEdit"} <= set(m.policy.disallowed)


def test_write_refused():
    with pytest.raises(ValueError):
        map_request(req(access="write"), cfg(), CAPS)


def test_owner_only_not_loaded_and_denied():
    m = map_request(req(("skill:closed", "mcp:gl", "command:cmd")), cfg(), CAPS)
    assert m.load.skills == () and m.load.mcp == () and m.load.commands == ()
    assert {"Skill(closed)", "Skill(cmd)", "mcp__gl"} <= set(m.policy.disallowed)
    assert "Skill(open)" not in m.policy.disallowed


def test_exposed_owner_item_loads_and_is_not_denied():
    m = map_request(req(("skill:closed",)), cfg(exposed=["skill:closed"]), CAPS)
    assert [n for n, _ in m.load.skills] == ["closed"]
    assert "Skill(closed)" not in m.policy.disallowed


def test_custom_deny_adds():
    m = map_request(req(), cfg(deny_rules=["Bash(rm:*)"]), CAPS)
    assert PUSH_DENY in m.policy.disallowed and "Bash(rm:*)" in m.policy.disallowed


@pytest.mark.parametrize("seed", range(20))
def test_property_non_owner(seed):
    import random

    r = random.Random(seed)  # noqa: S311
    ids = [c.id for c in CAPS]
    exposed = [i for i in ids if r.random() < 0.5]
    ask = [i for i in ids if r.random() < 0.7]
    m = map_request(req(tuple(ask), owner=False), cfg(exposed=exposed), CAPS)
    only = [c for c in CAPS if c.id not in exposed and not c.allowed_tools]
    rules = set(m.load.allowed_rules) | set(m.policy.allowed)
    for c in only:
        deny = f"mcp__{c.name}" if c.type == "mcp" else f"Skill({c.name})"
        assert deny in m.policy.disallowed
        assert deny not in rules
    assert m.policy.allowed == [] and m.policy.tools == []


def test_input_not_changed():
    c = cfg()
    ids = ("skill:open",)
    map_request(req(ids), c, CAPS)
    assert c.owner_tools == ["Read", "Grep", "Glob"] and c.deny_rules == []
