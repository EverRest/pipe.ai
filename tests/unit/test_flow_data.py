"""Data checks for flows/*.yaml and flows/tags.yaml."""

from pathlib import Path

import pytest
import yaml

FLOWS = Path(__file__).resolve().parents[2] / "flows"
NAMES = [
    "feature-dev", "bugfix", "planning", "brainstorm", "research",
    "test-run", "troubleshoot", "review-handoff", "delegate", "nightly",
]  # fmt: skip
BANNED = ("Read", "Bash", "mcp__", "claude:", "exec:", "wiz", "gitlab", "playwright")


def load(name):
    return yaml.safe_load((FLOWS / f"{name}.yaml").read_text())


def tag_of(step):
    cap = step.get("capability", "")
    return cap[4:] if cap.startswith("tag:") else None


def agent_steps(flow):
    return [s for s in flow["steps"] if not s["agent"].startswith("$starter")]


def test_exact_files():
    assert sorted(p.stem for p in FLOWS.glob("*.yaml")) == sorted(NAMES + ["tags"])


def test_tags_unique_and_valid():
    text = (FLOWS / "tags.yaml").read_text()
    data = yaml.safe_load(text)
    assert data["version"] == 1
    # safe_load hides duplicate keys, so count them in the text
    lines = text.splitlines()
    keys = [ln.strip(" :") for ln in lines if ln.startswith("  ") and ln[2] != " "]
    assert len(keys) == len(set(keys)) == len(data["tags"]) == 14
    for t in data["tags"].values():
        assert t["access"] in ("read", "write")
        assert 1 <= len(t["meaning"]) <= 120


@pytest.mark.parametrize("name", NAMES)
def test_template(name):
    tags = yaml.safe_load((FLOWS / "tags.yaml").read_text())["tags"]
    flow = load(name)
    assert flow["name"] == name
    assert "source" not in flow
    params = flow.get("params", {})
    steps = flow["steps"]
    assert len(agent_steps(flow)) <= 5
    for s in steps:
        assert "source" not in s
        tag = tag_of(s)
        if tag and tag.startswith("$"):
            assert all(v in tags for v in params[tag[1:]]["values"])
        elif tag:
            assert tag in tags
        else:
            assert s["agent"] in ("any", "$starter", "$agent")
    ids = [s["id"] for s in steps]
    for i, s in enumerate(steps):
        if "on_fail" in s:
            assert s["agent"] != "$starter"
            assert ids.index(s["on_fail"]) > i
    raw = (FLOWS / f"{name}.yaml").read_text()
    for word in BANNED:
        assert word not in raw
