from pipe.core.capability import Capability, Notice
from pipe.core.summary import build_summary, decide_dm

CAPS = [
    Capability(id="skill:a", name="a", open=True),
    Capability(id="skill:b", name="b"),
    Capability(id="repo:r", name="r", role="listed_only"),
]
N = [
    Notice("unknown_id", "x:1", "x:1 is in exposed but not discovered."),
    Notice("skipped", "s:2", "s:2 was skipped."),
]


def test_text():
    s = build_summary(CAPS, [], N)
    lines = s.text.splitlines()
    assert lines[0] == "1 exposed, 2 owner-only, 1 skipped"
    assert lines[1:] == [
        "skipped: s:2 was skipped.",
        "unknown_id: x:1 is in exposed but not discovered.",
    ]
    assert "hidden" not in s.text


def test_hash():
    a = build_summary(CAPS, [], N)
    assert build_summary(CAPS[::-1], [], N[::-1]) == a
    assert build_summary(CAPS, ["skill:b"], N).hash != a.hash
    assert build_summary(CAPS, [], N[:1]).hash != a.hash


def test_scrub():
    n = [Notice("unknown_id", "xoxb-123-abc-def", "xoxb-123-abc-def is gone.")]
    assert "xoxb" not in build_summary([], [], n).text


def test_decide():
    assert decide_dm("h", None) == "send"
    assert decide_dm("h", "h") == "none"
    assert decide_dm("h", "g") == "send"
