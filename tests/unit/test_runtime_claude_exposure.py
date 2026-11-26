from pipe.runtime_claude_capability import ClaudeCapability
from pipe.runtime_claude_exposure import SAFE_TOOLS, classify, to_core


def cap(type="skill", tools=("Read",), signals=(), **kw):
    return ClaudeCapability(
        id=f"{type}:p:a", type=type, name="a", allowed_tools=tools, signals=signals, **kw
    )


def test_classify():
    assert classify(cap()) == "open"
    assert classify(cap("command", tools=("Read", "Grep"))) == "open"
    assert classify(cap(tools=None)) == "owner-only"
    for t in ("Bash", "WebFetch", "mcp__x"):
        assert classify(cap(tools=("Read", t))) == "owner-only"
    assert classify(cap(signals=("curl",))) == "owner-only"
    assert classify(cap(tools=())) == "owner-only"
    for t in ("mcp", "plugin", "repo"):
        assert classify(cap(t)) == "owner-only"
    assert "Bash" not in SAFE_TOOLS
    assert {"Read", "Grep", "Glob"} == SAFE_TOOLS
    for t in ("Edit", "Write", "NotebookEdit"):
        assert classify(cap(tools=("Read", t))) == "owner-only"


def test_to_core():
    c = cap(plugin="p", plugin_id="plugin:p", declared_tags=("review",))
    k = to_core(c)
    assert (k.id, k.role, k.open, k.group) == (c.id, "item", True, "plugin:p")
    assert k.tags == ("skill", "p") and k.declared_tags == ("review",)
    assert (k.runtime, k.access, k.classified) == ("claude", None, True)
    assert to_core(cap(tools=None)).open is False
    m = to_core(cap("mcp"))
    assert (m.role, m.open, m.group, m.tags) == ("item", False, None, ("mcp",))
    assert to_core(cap("plugin")).role == "group"
    assert to_core(cap("repo")).role == "listed_only"
    assert to_core(c) == k and c.declared_tags == ("review",)
