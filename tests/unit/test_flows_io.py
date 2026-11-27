from pipe.flows_io import load_flows, load_tags

TAGS = (
    "version: 1\ntags:\n  e2e: {access: read, meaning: x}\n"
    "  implement: {access: write, meaning: y}\n"
)


def tpl(name="bugfix", tag="e2e", extra=""):
    return f"""# comment
name: {name}
version: 1
description: "d {tag}"
steps:
  - id: a
    agent: any
    capability: "tag:{tag}"
    goal: g
{extra}"""


def setup(tmp_path, shared=None, over=None):
    s, o = tmp_path / "flows", tmp_path / "home" / "flows"
    s.mkdir()
    (s / "tags.yaml").write_text(TAGS)
    for d, files in ((s, shared or {}), (o, over or {})):
        if files:
            d.mkdir(parents=True, exist_ok=True)
        for k, v in files.items():
            (d / k).write_text(v)
    return s, o


def test_load_tags(tmp_path):
    s, _ = setup(tmp_path)
    assert load_tags(s / "tags.yaml") == {"e2e": "read", "implement": "write"}


def test_shared_and_override_wins(tmp_path):
    s, o = setup(tmp_path, {"bugfix.yaml": tpl()}, {"bugfix.yaml": tpl(tag="implement")})
    f = load_flows(s, o)
    assert f["bugfix"].origin == "override" and f["bugfix"].tags == {"implement"}
    assert load_flows(s, tmp_path / "none")["bugfix"].origin == "git"


def test_bad_override_does_not_hide_shared(tmp_path):
    s, o = setup(tmp_path, {"bugfix.yaml": tpl()}, {"bugfix.yaml": tpl(tag="nope")})
    errs = []
    f = load_flows(s, o, errors=errs)
    assert f["bugfix"].origin == "git"
    assert errs and all("bugfix" in e for e in errs) and not any("nope" in e for e in errs)


def test_refusals(tmp_path):
    big = tpl() + "# " + "x" * 21000
    obj = "name: !!python/object/apply:os.system [x]\n"
    s, o = setup(
        tmp_path,
        {
            "big.yaml": big,
            "obj.yaml": obj,
            "stem.yaml": tpl("other"),
            "notes.txt": "x",
            "bad.yaml": "a: [",
            "fixed.yaml": tpl("fixed").replace("agent: any", "agent: B123"),
        },
    )
    errs = []
    assert load_flows(s, o, errors=errs) == {}
    assert len(errs) >= 5 and not any("B123" in e or "system" in e for e in errs)


def test_no_write(tmp_path):
    s, o = setup(tmp_path, {"bugfix.yaml": tpl()})
    snap = lambda: sorted((str(p), p.stat().st_mtime_ns) for p in tmp_path.rglob("*"))  # noqa: E731
    before = snap()
    load_flows(s, o)
    assert snap() == before


def test_missing_dirs(tmp_path):
    assert load_flows(tmp_path / "a", tmp_path / "b", tags={"e2e": "read"}) == {}
