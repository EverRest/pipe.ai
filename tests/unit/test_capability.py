import dataclasses
import pathlib

import pytest

from pipe.core.capability import Capability, Notice, sanitize_tags


def test_defaults_and_frozen():
    c = Capability(id="a:b", name="B")
    assert (c.runtime, c.access, c.input_schema, c.output_schema, c.classified) == (
        "claude",
        None,
        None,
        None,
        True,
    )
    assert c.role == "item" and c.open is False and c.group is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.id = "x"  # type: ignore[misc]


@pytest.mark.parametrize("kw", [{"id": ""}, {"name": ""}, {"role": "other"}])
def test_invalid(kw):
    with pytest.raises(ValueError):
        Capability(**{"id": "a:b", "name": "B", **kw})


def test_notice():
    assert Notice("unknown_id", "a:b", "t").kind == "unknown_id"


def test_sanitize_tags():
    raw = ["ok", "Bad", "ok", "a b", "x" * 33, "x" * 32, "y_z", "a-1"]
    assert sanitize_tags(raw) == ("ok", "x" * 32, "a-1")
    assert len(sanitize_tags([f"t{i}" for i in range(20)])) == 8
    assert isinstance(sanitize_tags([]), tuple)


def test_no_adapter_terms():
    import pipe.core.capability as m

    src = pathlib.Path(m.__file__).read_text().lower()
    for w in ("claude", "plugin", "skill", "mcp"):
        assert w not in src.replace('runtime: str = "claude"', "")


def test_sanitize_tags_accepts_none():
    from pipe.core.capability import sanitize_tags

    assert sanitize_tags(None) == ()
