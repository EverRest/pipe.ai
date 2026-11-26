import copy
import pathlib

from pipe.core.schema import check_schema, validate_schema

S = {
    "type": "object",
    "required": ["repo"],
    "additionalProperties": False,
    "properties": {
        "repo": {"type": "string", "minLength": 2, "maxLength": 5},
        "n": {"type": "integer", "minimum": 1, "maximum": 3},
        "k": {"enum": ["a", "b"]},
        "l": {"type": "array", "items": {"type": "string"}},
    },
    "title": "t",
    "description": "d",
}


def test_check_ok():
    assert check_schema(S) == []


def test_check_bad():
    for bad in (
        {"$ref": "#"},
        {"oneOf": []},
        {"anyOf": []},
        {"pattern": "x"},
        {"format": "uri"},
        {"additionalProperties": {}},
        {"type": "date"},
        {"description": "x" * 2001},
        {"properties": {"a": {"items": {"items": {"items": {"items": {"items": {}}}}}}}},
        {"properties": {"a": {"$ref": "#"}}},
    ):
        assert check_schema(bad), bad


def test_validate_ok():
    assert validate_schema({"repo": "abc", "n": 2, "k": "a", "l": ["x"]}, S) == []


def test_validate_errors():
    cases = [
        ({"repo": 1}, "payload.repo: expected string"),
        ({}, "payload.repo: missing"),
        ({"repo": "ab", "z": 1}, "payload: unexpected key"),
        ({"repo": "ab", "k": "SECRET"}, "payload.k: not in enum"),
        ({"repo": "a"}, "payload.repo: too short"),
        ({"repo": "abcdefg"}, "payload.repo: too long"),
        ({"repo": "ab", "n": 0}, "payload.n: below minimum"),
        ({"repo": "ab", "n": 9}, "payload.n: above maximum"),
        ({"repo": "ab", "n": True}, "payload.n: expected integer"),
        ({"repo": "ab", "l": [1]}, "payload.l[0]: expected string"),
    ]
    for inst, msg in cases:
        errs = validate_schema(inst, S)
        assert msg in errs, (inst, errs)
        assert not any("SECRET" in e for e in errs)
    assert validate_schema(True, {"type": "number"}) == ["payload: expected number"]


def test_pure_and_stdlib():
    s, i = copy.deepcopy(S), {"repo": "ab"}
    check_schema(s)
    validate_schema(i, s)
    assert s == S and i == {"repo": "ab"}
    import pipe.core.schema as m

    src = pathlib.Path(m.__file__).read_text()
    assert len(src.splitlines()) < 80
    for w in ("plugin", "skill", "mcp"):
        assert w not in src.lower()
