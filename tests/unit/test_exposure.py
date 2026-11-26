from pipe.core.capability import Capability, Notice
from pipe.core.exposure import exposed_by, exposure_notices, render_list, state_of


def item(id, open=False, group=None, **kw):
    return Capability(id=id, name=id.split(":")[-1], role="item", open=open, group=group, **kw)


GRP = Capability(id="plugin:p", name="p", role="group")
REPO = Capability(id="repo:r", name="r", role="listed_only")


def test_listed_only_and_group():
    assert state_of(REPO, ["repo:r"]) == "owner-only"
    assert state_of(GRP, []) == "owner-only"
    assert state_of(GRP, ["plugin:p"]) == "exposed"


def test_clean_and_owner():
    clean, dirty = item("skill:a", open=True), item("skill:b")
    assert (state_of(clean, []), exposed_by(clean, [])) == ("exposed", "clean")
    assert (state_of(dirty, []), exposed_by(dirty, [])) == ("owner-only", None)
    assert (state_of(dirty, ["skill:b"]), exposed_by(dirty, ["skill:b"])) == ("exposed", "owner")
    assert exposed_by(clean, ["skill:a"]) == "owner"  # path A: stays when it stops being open


def test_group_exposes_items():
    a, b = item("skill:a", group="plugin:p"), item("skill:b", open=True, group="plugin:q")
    assert state_of(a, ["plugin:p"]) == "exposed" and exposed_by(a, ["plugin:p"]) == "owner"
    assert state_of(item("skill:c", group="plugin:q"), ["plugin:p"]) == "owner-only"
    assert exposed_by(b, ["plugin:p"]) == "clean"
    assert state_of(a, []) == "owner-only"


def test_no_mutation():
    ex = ["skill:a"]
    state_of(item("skill:a"), ex)
    assert ex == ["skill:a"]


def kinds(ns):
    return sorted((n.kind, n.id) for n in ns)


def test_notices():
    caps = [
        item("skill:a", group="plugin:p"),
        item("skill:ok", open=True),
        GRP,
        REPO,
        item("exec:x", classified=False),
    ]
    ex = ["plugin:p", "repo:r", "gone:1", "exec:x"]
    ns = exposure_notices(caps, ex, {"skill:a": ["x"], "nope:1": ["x"]})
    assert kinds(ns) == [
        ("credential_exposed", "skill:a"),
        ("not_exposable", "repo:r"),
        ("unknown_id", "gone:1"),
        ("unknown_tag_id", "nope:1"),
    ]
    assert exposure_notices(caps, [], {}) == []
    assert all("/" not in n.text.replace(n.id, "") and "http" not in n.text for n in ns)


def test_render_list():
    caps = [item("skill:b", open=True), item("mcp:g"), REPO, GRP]
    out = render_list(
        caps, ["plugin:p"], [Notice("unknown_id", "x:1", "x:1 is in exposed but not discovered.")]
    )
    assert [r.split()[:3] for r in out[:4]] == [
        ["owner-only", "mcp", "mcp:g"],
        ["exposed", "plugin", "plugin:p"],
        ["owner-only", "repo", "repo:r"],
        ["exposed", "skill", "skill:b"],
    ]
    assert out[4] == "" and out[5] == "4 capabilities: 2 exposed, 2 owner-only."
    assert out[-1] == "NOTICE unknown_id: x:1 is in exposed but not discovered."
    assert render_list([], [], []) == ["0 capabilities"]
