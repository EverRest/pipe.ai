"""The ten shipped templates expand to valid, verified plans (FR-029, SC-001, SC-011)."""

import os
from types import SimpleNamespace as NS

import pytest

from flow_kit import FLOWS, TAGS
from pipe.core.flows import expand, missing_tags
from pipe.core.pipeline import validate_plan
from pipe.core.source import effective_source, hop_limit
from pipe.flows_io import load_flows

ALL = load_flows(FLOWS, FLOWS / "none", TAGS)
CARDS = {
    k: NS(
        bot_id=k,
        owner=f"O{k}",
        kind="agent",
        name=k,
        skills=[{"id": f"{t}-{k}", "tags": [t], "access": a} for t, a in TAGS.items()],
    )  # fmt: skip
    for k in ("B1", "B2")
}
# name: (tags in order, count of human steps, extra checks by step index)
SHAPE = {
    "feature-dev": (["decompose", "implement", "e2e", "review"], 1),
    "bugfix": (["reproduce", "implement", "e2e", "review"], 1),
    "test-run": (["e2e", "troubleshoot"], 0),
    "troubleshoot": (["collect", "diagnose", "implement"], 1),
    "review-handoff": (["review", "implement", "review"], 1),
    "planning": (["brainstorm", "spec", "decompose"], 0),
    "brainstorm": (["context", "brainstorm", "summarize"], 0),
    "research": (["research", "summarize"], 0),
    "nightly": (["e2e", "troubleshoot"], 0),
}


def plan(name, **kw):
    return expand(ALL[name], "goal", starter="U9", agent=kw.pop("agent", None), cards=CARDS, **kw)


def test_exactly_ten_templates_and_hash_is_stable():
    assert sorted(ALL) == sorted([*SHAPE, "delegate"]) and len(ALL) == 10
    assert all(len(f.steps) <= 6 and f.tags <= set(TAGS) for f in ALL.values())


@pytest.mark.parametrize("name", sorted(ALL))
def test_expands_validates_and_is_verified(name):
    p = plan(name, agent="B2" if name == "delegate" else None)
    assert validate_plan(p, CARDS, "U9", ALL) == []
    ns = NS(steps=p["steps"], source=p["source"])
    assert effective_source(ns, ALL, CARDS, "U9") == "template"
    assert hop_limit("template") == 5
    assert sum(s["agent"] == "any" or s["agent"] == "B2" for s in p["steps"]) <= 5


@pytest.mark.parametrize("name", sorted(SHAPE))
def test_shape(name):
    tags, humans = SHAPE[name]
    steps = plan(name)["steps"]
    agents = [s for s in steps if not s["agent"].startswith("human:")]
    assert [s["capability"][4:] for s in agents] == tags
    assert len(steps) - len(agents) == humans


def test_special_steps():
    s = plan("feature-dev")["steps"]
    assert s[0]["gate"] == "approval" and s[3]["exclude_agents_of"] == [1]
    assert plan("review-handoff")["steps"][2]["exclude_agents_of"] == [1]
    assert plan("planning")["steps"][2]["gate"] == "approval"
    assert plan("test-run")["steps"][0]["on_fail"] == 1
    assert (
        plan("nightly", params={"check": "deps-check"})["steps"][0]["capability"]
        == "tag:deps-check"
    )
    d = plan("delegate", agent="B2")["steps"][0]
    assert d["agent"] == "B2" and d["access"] == "write" and d["capability"] == "implement-B2"
    assert all(s["access"] == "read" for n in ("brainstorm", "research") for s in plan(n)["steps"])


@pytest.mark.parametrize("name", sorted(SHAPE))
def test_removing_a_tag_card_names_the_tag(name):
    tag = SHAPE[name][0][0]
    cards = {k: NS(skills=[e for e in c.skills if tag not in e["tags"]]) for k, c in CARDS.items()}
    assert missing_tags(ALL[name], cards)[0] == tag


def test_files_are_not_changed_by_a_run():
    before = {p: os.stat(p).st_mtime_ns for p in FLOWS.glob("*.yaml")}
    load_flows(FLOWS, FLOWS / "none", TAGS)
    assert before == {p: os.stat(p).st_mtime_ns for p in FLOWS.glob("*.yaml")}
