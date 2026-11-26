import copy
import dataclasses

import pytest

from pipe.core.capability import Capability
from pipe.core.card import CardError, Identity, build_card, validate_card

ID = Identity("agent", "desc", "U1", "B1", "U2BOT")


def cap(id, open=False, group=None, role="item", **kw):
    return Capability(
        id=id, name=id.split(":")[-1], description="d", role=role, open=open, group=group, **kw
    )


CAPS = [
    cap("skill:b", open=True, tags=("skill",), declared_tags=("review",)),
    cap("skill:a", tags=("skill",)),
    cap("skill:g", group="plugin:p"),
    cap("plugin:p", role="group"),
    cap("repo:r", role="listed_only"),
]


def ids(card):
    return [s["id"] for s in card.skills]


def test_shape_and_clean():
    c = build_card(ID, CAPS, [], {})
    assert (c.name, c.description, c.owner, c.bot_id, c.bot_user_id, c.kind, c.mode) == (
        "agent",
        "desc",
        "U1",
        "B1",
        "U2BOT",
        "agent",
        "laptop",
    )
    assert ids(c) == ["skill:b"]
    assert c.skills[0] == {
        "id": "skill:b",
        "name": "b",
        "description": "d",
        "tags": ["skill", "review"],
    }
    assert validate_card(c) == []


def test_owner_exposure_and_group():
    assert ids(build_card(ID, CAPS, ["skill:a"], {})) == ["skill:a", "skill:b"]
    assert ids(build_card(ID, CAPS, ["plugin:p"], {})) == ["skill:b", "skill:g"]
    assert ids(build_card(ID, CAPS, ["repo:r", "plugin:p"], {})) == ["skill:b", "skill:g"]
    # path B: clean item that stops being open leaves; path A stays
    dirty = [dataclasses.replace(CAPS[0], open=False)]
    assert ids(build_card(ID, dirty, [], {})) == []
    assert ids(build_card(ID, dirty, ["skill:b"], {})) == ["skill:b"]


def test_empty_and_errors():
    assert build_card(ID, [], [], {}).skills == []
    for kw in ({"owner": ""}, {"bot_id": ""}, {"bot_user_id": ""}):
        with pytest.raises(CardError):
            build_card(dataclasses.replace(ID, **kw), CAPS, [], {})


def test_tag_map_changes_hash_and_order_does_not():
    h = build_card(ID, CAPS, [], {}).hash
    assert build_card(ID, CAPS[::-1], [], {}).hash == h
    assert build_card(ID, CAPS, [], {"skill:b": ["x"]}).hash != h
    assert build_card(ID, CAPS, [], {"skill:b": ["x"]}).skills[0]["tags"] == ["skill", "x"]


def test_hash_ignores_card_fields():
    h = build_card(ID, CAPS, [], {}).hash
    other = dataclasses.replace(ID, description="other", owner="U9", bot_user_id="U9BOT")
    assert build_card(other, CAPS, [], {}).hash == h


def test_sanitized():
    bad = cap("skill:z", open=True)
    bad = dataclasses.replace(
        bad, name="n https://x.io/a", description="see /Users/a/b and xoxb-123-abc-def"
    )
    c = build_card(ID, [bad], [], {})
    assert validate_card(c) == []
    s = str(c)
    assert "https" not in s and "/Users" not in s and "xoxb" not in s


def test_validate_violations():
    c = build_card(ID, CAPS, [], {})
    for field, val in (
        ("description", "http://x.io"),
        ("name", "/Users/a/b"),
        ("owner", "xoxb-123-abc-def"),
    ):
        assert validate_card(dataclasses.replace(c, **{field: val}))
    sk = [{**c.skills[0], "description": "https://x"}]
    assert validate_card(dataclasses.replace(c, skills=sk))


def test_bot_user_id_form():
    c = build_card(ID, CAPS, [], {})
    assert validate_card(dataclasses.replace(c, bot_user_id="<@U1>"))
    assert validate_card(dataclasses.replace(c, bot_user_id="x"))
    # changing bot_user_id alone keeps the hash (known limit)
    assert build_card(dataclasses.replace(ID, bot_user_id="U3BOT"), CAPS, [], {}).hash == c.hash


DECL = Capability(
    id="exec:lint",
    name="Lint",
    description="d",
    role="item",
    classified=False,
    runtime="exec",
    tags=("exec",),
    access="read",
    input_schema={"type": "object", "properties": {"repo": {"type": "string"}}},
    output_schema={"type": "object"},
)


def test_declared_entry():
    c = build_card(ID, [DECL], ["exec:lint"], {})
    e = c.skills[0]
    assert (
        e["access"] == "read"
        and e["input_schema"] == DECL.input_schema
        and e["output_schema"] == {"type": "object"}
    )
    assert not {"runtime", "command", "url", "token", "env_allow", "timeout_s"} & set(e)
    assert ids(build_card(ID, [DECL], [], {})) == []
    bare = dataclasses.replace(DECL, access=None, input_schema=None, output_schema=None)
    e = build_card(ID, [bare], ["exec:lint"], {}).skills[0]
    assert not {"access", "input_schema", "output_schema"} & set(e)
    changed = dataclasses.replace(DECL, input_schema={"type": "string"})
    assert build_card(ID, [changed], ["exec:lint"], {}).hash != c.hash


def test_schema_scan():
    c = build_card(ID, [DECL], ["exec:lint"], {})
    for v in ("https://x.io", "xoxb-123-abc-def", "/Users/a/b"):
        e = {**c.skills[0], "input_schema": {"type": "object", "description": v}}
        assert validate_card(dataclasses.replace(c, skills=[e]))


def test_wire_names():
    c = build_card(ID, CAPS, [], {})
    d = dataclasses.asdict(c)
    assert {"bot_id", "bot_user_id", "owner"} <= set(d)
    assert validate_card(d) == []
    for old, new in (("bot_id", "agent_id"), ("bot_user_id", "handle"), ("owner", "owner_id")):
        w = copy.deepcopy(d)
        w[new] = w.pop(old)
        assert validate_card(w)
