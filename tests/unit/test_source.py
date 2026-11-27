import ast
from pathlib import Path
from types import SimpleNamespace as NS

from pipe.core import source
from pipe.core.source import (
    MAX_HOP_FREE,
    MAX_HOP_TEMPLATE,
    effective_source,
    hop_limit,
    parse_source,
)

H = "a" * 32


class FakeFlow:
    def __init__(self, hash=H, ok=True):
        self.hash, self.ok = hash, ok

    def matches(self, steps, cards, starter):
        return self.ok


def plan(src=f"template:bugfix@{H}"):
    return NS(steps=("s",), source=src)


def test_limits():
    assert (MAX_HOP_FREE, MAX_HOP_TEMPLATE) == (3, 5)
    assert hop_limit("free") == 3
    assert hop_limit("template") == 5
    assert not hasattr(source, "MAX_HOP")


def test_parse_ok():
    assert parse_source(f"template:bugfix@{H}") == ("bugfix", H)


def test_parse_bad():
    for s in (
        "free",
        None,
        "",
        "template:",
        "template:Bug@abc",
        f"template:bug@{'a' * 31}",
        f"template:bug@{'a' * 33}",
        f"template:bug@{'A' * 32}",
        f"template:bug@{H}\n",
        f"template:{'a' * 33}@{H}",
        7,
    ):
        assert parse_source(s) is None, s


def test_effective_template():
    assert effective_source(plan(), {"bugfix": FakeFlow()}, {}, "U1") == "template"


def test_effective_free():
    f = {"bugfix": FakeFlow()}
    assert effective_source(plan(None), f, {}, "U1") == "free"
    assert effective_source(plan("free"), f, {}, "U1") == "free"
    assert effective_source(plan(f"template:other@{H}"), f, {}, "U1") == "free"
    assert effective_source(plan(), {"bugfix": FakeFlow("b" * 32)}, {}, "U1") == "free"
    assert effective_source(plan(), {"bugfix": FakeFlow(ok=False)}, {}, "U1") == "free"
    assert effective_source(plan(), {}, {}, "U1") == "free"
    assert effective_source(plan(), None, {}, "U1") == "free"


def test_effective_never_raises():
    class Boom(FakeFlow):
        def matches(self, *a):
            raise RuntimeError

    assert effective_source(plan(), {"bugfix": Boom()}, {}, "U1") == "free"
    assert effective_source(plan("\x00" * 5000), {"bugfix": FakeFlow()}, {}, "U1") == "free"
    assert effective_source(NS(steps=()), {"bugfix": FakeFlow()}, {}, "U1") == "free"


def test_no_input_change():
    p, f = plan(), {"bugfix": FakeFlow()}
    effective_source(p, f, {}, "U1")
    assert p.source == f"template:bugfix@{H}" and list(f) == ["bugfix"]


def test_imports_clean():
    tree = ast.parse(Path(source.__file__).read_text())
    mods = {
        n.module if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        for a in getattr(n, "names", [])
    }
    assert mods <= {"re"}
