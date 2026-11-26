from pipe.core.capability import Capability
from pipe.core.card import resolve_tags

C = Capability(id="skill:a", name="a", tags=("skill", "p"), declared_tags=("fm", "skill"))


def test_resolve():
    assert resolve_tags(C, {}) == ("skill", "p", "fm")
    assert resolve_tags(C, {"skill:a": ["review", "p"]}) == ("skill", "p", "review")
    assert resolve_tags(C, {"skill:a": []}) == ("skill", "p")
    assert resolve_tags(C, {"skill:b": ["x"]}) == ("skill", "p", "fm")
    bare = Capability(id="skill:w", name="w", tags=("skill",))
    assert resolve_tags(bare, {"skill:w": ["review"]}) == ("skill", "review")
    assert resolve_tags(C, {"skill:a": [f"t{i}" for i in range(12)] + ["Bad"]}) == (
        "skill",
        "p",
    ) + tuple(f"t{i}" for i in range(8))


def test_pure():
    m = {"skill:a": ["x"]}
    resolve_tags(C, m)
    assert m == {"skill:a": ["x"]}
