import pytest

from pipe.runtime_claude_capability import (
    ClaudeCapability,
    assign_ids,
    find_signals,
    from_text,
    parse_frontmatter,
)


def cap(type="skill", name="a", plugin=None, source="/s/a", **kw):
    return ClaudeCapability(id="", type=type, name=name, plugin=plugin, source=source, **kw)


def test_parse_frontmatter():
    fm, body = parse_frontmatter("---\nname: x\ndescription: >\n  one\n  two\n---\nbody\n")
    assert fm == {"name": "x", "description": "one two\n"}
    assert body == "body\n"
    assert parse_frontmatter("plain") == ({}, "plain")
    with pytest.raises(ValueError):
        parse_frontmatter("---\na: [unclosed\n---\nb")


def test_from_text_tags_and_tools():
    c = from_text(
        "skill", "dir", "---\ntags: [review, Bad Tag]\nallowed-tools: Read, Grep\n---\nhi", "/p"
    )
    assert c.name == "dir" and c.declared_tags == ("review",)
    assert c.allowed_tools == ("Read", "Grep") and c.signals == ()
    c = from_text("skill", "dir", "---\nname: n\n---\nhi", "/p")
    assert c.name == "n" and c.allowed_tools is None and c.declared_tags == ()
    assert from_text("command", "cmd", "---\nname: n\n---\nx", "/p").name == "cmd"


@pytest.mark.parametrize(
    "text,sig",
    [
        ("use mcp__x", "mcp__"),
        ("see https://a.b", "url"),
        ("a TOKEN", "token"),
        ("API Key", "api key"),
        ("Password", "password"),
        ("OAuth", "oauth"),
        ("read .env", ".env"),
        ("GH_TOKEN", "env-secret"),
        ("run curl x", "curl"),
        ("git push now", "git push"),
        ("run kubectl get", "kubectl"),
    ],
)
def test_find_signals(text, sig):
    assert sig in find_signals(text)


def test_find_signals_plain_and_names_only():
    assert find_signals("Summarize this text. Be nice.") == ()
    assert all(" " not in s or s in ("api key", "git push") for s in find_signals("secret curl"))
    assert "secret" in find_signals("SECRET")


def test_assign_ids_basic():
    out = assign_ids(
        [
            cap("skill", "a"),
            cap("skill", "b", plugin="p", source="/p/skills/b"),
            cap("command", "c"),
            cap("mcp", "m"),
            cap("plugin", "p", source="/p"),
            cap("repo", "r"),
        ]
    )
    assert {c.id for c in out} == {
        "skill:a", "skill:p:b", "command:c", "mcp:m", "plugin:p", "repo:r",
    }  # fmt: skip
    assert next(c for c in out if c.name == "b").plugin_id == "plugin:p"


def test_assign_ids_collision_stable():
    a, b = cap(name="x", plugin="p", source="/m1/p/x"), cap(name="x", plugin="p", source="/m2/p/x")
    c = cap(name="y")
    o1, o2 = assign_ids([a, b, c]), assign_ids([c, b, a])
    ids = {x.source: x.id for x in o1}
    assert ids == {x.source: x.id for x in o2}
    assert all(
        i.startswith("skill:p:x#") and len(i.split("#")[1]) == 6
        for s, i in ids.items()
        if s != "/s/a"
    )
    assert ids["/s/a"] == "skill:y"
    assert {x.source: x.id for x in assign_ids(o1)} == ids  # idempotent


def test_id_ignores_description_and_path():
    a = assign_ids([cap(description="one")])[0]
    b = assign_ids([cap(description="two", source="/elsewhere")])[0]
    assert a.id == b.id == "skill:a"
