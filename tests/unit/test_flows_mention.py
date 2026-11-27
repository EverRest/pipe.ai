"""parse_flow_mention and missing_tags (flow-mention contract)."""

from types import SimpleNamespace as NS

import pytest

from pipe.core.flows import expand, missing_tags, parse_flow
from pipe.core.flows import parse_flow_mention as parse

USERS = {"UA": "B1", "UB": "B2"}
TAGS = {"e2e": "read", "implement": "write", "deps": "read"}


def test_plain_and_params_and_agents():
    m = parse("<@UA>  flow:nightly check=deps  run   it <@UB>", USERS)
    assert (m.name, m.params, m.goal) == ("nightly", {"check": "deps"}, "run it")
    assert m.agents == ["B1", "B2"]


def test_params_end_at_first_other_word():
    m = parse("flow:x a=b goal c=d", {})
    assert m.params == {"a": "b"} and m.goal == "goal c=d"


@pytest.mark.parametrize("text", ["no word", "flow:BAD x", "", None])
def test_none(text):
    assert parse(text, {}) is None


def test_only_the_first_flow_word_counts():
    m = parse("flow:a fix flow:b", {})
    assert m.name == "a" and m.goal == "fix flow:b"


def card(*skills):
    return NS(skills=[{"id": f"c-{t}", "tags": [t], "access": TAGS[t]} for t in skills])


def flow(*steps):
    data = {
        "name": "f", "version": 1, "description": "d",
        "steps": [{"id": f"s{i}", "agent": "any", "capability": f"tag:{t}", "goal": "g"}
                  for i, t in enumerate(steps)],
    }  # fmt: skip
    return parse_flow(data, "f", TAGS)


def test_missing_tags_in_order():
    f = flow("e2e", "implement", "deps")
    assert missing_tags(f, {"B1": card("implement")}) == ["e2e", "deps"]
    assert missing_tags(f, {"B1": card("e2e", "implement", "deps")}) == []


def test_expand_param_messages():
    with pytest.raises(ValueError, match="unknown parameter zz"):
        expand(flow("e2e"), params={"zz": "a"})
