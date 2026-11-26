import copy

from pipe.core.capability import Capability
from pipe.core.card import resolve_tags
from pipe.core.exposure import exposed_by, exposure_notices, state_of
from pipe.declared import declared_caps

E = {
    "id": "lint-repo",
    "runtime": "exec",
    "name": "Lint",
    "description": "Lint a repo",
    "access": "read",
    "tags": ["ci", "Bad"],
    "command": ["/opt/secret-bin"],
    "env_allow": ["SECRET_VAR"],
    "timeout_s": 5,
    "input_schema": {"type": "object"},
}
H = {
    "id": "deploys",
    "runtime": "http",
    "name": "D",
    "description": "d",
    "access": "read",
    "url": "https://api.example.com/x",
    "token": "keychain:svc",
}


def test_fields():
    snap = copy.deepcopy([E, H])
    a, b = declared_caps([E, H])
    assert snap == [E, H]
    assert a == Capability(
        "exec:lint-repo", "Lint", "Lint a repo", "item", False, None, ("exec",), ("ci",),
        "exec", "read", {"type": "object"}, None, False,
    )  # fmt: skip
    assert b.id == "http:deploys" and b.tags == ("http",) and b.input_schema is None
    for v in ("/opt/secret-bin", "SECRET_VAR", "api.example.com", "keychain:svc"):
        assert v not in repr([a, b])


def test_accepts_config_object():
    class C:
        capabilities = [E]

    assert [c.id for c in declared_caps(C())] == ["exec:lint-repo"]


def test_exposure_only_by_owner():
    c = declared_caps([E])[0]
    assert state_of(c, []) == "owner-only"
    assert state_of(c, ["exec:lint-repo"]) == "exposed"
    assert exposed_by(c, ["exec:lint-repo"]) == "owner"


def test_notices_and_tags():
    caps = declared_caps([E])
    kinds = {(n.kind, n.id) for n in exposure_notices(caps, ["exec:lint-repo", "exec:nope"], {})}
    assert kinds == {("unknown_id", "exec:nope")}
    assert resolve_tags(caps[0], {"exec:lint-repo": ["x"]}) == ("exec", "x")
