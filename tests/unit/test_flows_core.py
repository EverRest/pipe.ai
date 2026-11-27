import copy
from types import SimpleNamespace as NS

import pytest

from pipe.core.flows import expand, flow_hash, parse_flow, validate_flow
from pipe.core.source import effective_source

TAGS = {"reproduce": "read", "implement": "write", "review": "read", "e2e": "read", "deps": "read"}


def data():
    return {
        "name": "bugfix",
        "version": 1,
        "description": "Fix a bug.",
        "params": {"check": {"values": ["e2e", "deps"], "default": "e2e"}},
        "steps": [
            {"id": "repro", "agent": "any", "capability": "tag:reproduce", "goal": "Test {goal}"},
            {
                "id": "fix",
                "agent": "any",
                "capability": "tag:implement",
                "gate": "approval",
                "goal": "Fix",
            },
            {
                "id": "chk",
                "agent": "any",
                "capability": "tag:$check",
                "goal": "Check {check}",
                "exclude_agents_of": ["fix"],
                "on_fail": "rev",
            },
            {"id": "rev", "agent": "any", "capability": "tag:review", "goal": "Review"},
        ],
    }


def errs(d, stem="bugfix"):
    return validate_flow(d, stem, TAGS)


def test_valid():
    assert errs(data()) == []


def test_hash_ignores_key_order_and_is_content_sensitive():
    d = data()
    rev = dict(reversed(list(d.items())))
    assert flow_hash(d) == flow_hash(rev) and len(flow_hash(d)) == 32
    e = copy.deepcopy(d)
    e["steps"][0]["goal"] += "x"
    assert flow_hash(e) != flow_hash(d)


def mut(f):
    d = data()
    f(d)
    return d


BAD = {
    "extra_key": lambda d: d.update(x=1),
    "stem": lambda d: d.update(name="other"),
    "fixed_agent": lambda d: d["steps"][0].update(agent="B123"),
    "unknown_tag": lambda d: d["steps"][0].update(capability="tag:nope"),
    "access": lambda d: d["steps"][0].update(access="write"),
    "six_agents": lambda d: d["steps"].extend(
        [{"id": f"s{i}", "agent": "any", "capability": "tag:e2e", "goal": "g"} for i in range(3)]
    ),
    "two_on_fail": lambda d: d["steps"][0].update(on_fail="rev"),
    "loop": lambda d: d["steps"][2].update(on_fail="repro"),
    "human_on_fail": lambda d: d["steps"].append(
        {"id": "h", "agent": "$starter", "access": "approve", "goal": "ok", "on_fail": "rev"}
    ),
    "url": lambda d: d["steps"][0].update(goal="see http://x.io"),
    "path": lambda d: d["steps"][0].update(goal="see /Users/bob/x"),
    "token": lambda d: d["steps"][0].update(goal="xoxb-123456789-abcdef"),
    "unused_param": lambda d: d["params"].update(zz={"values": ["e2e", "deps"], "default": "e2e"}),
    "bad_placeholder": lambda d: d["steps"][0].update(goal="{nope}"),
}


@pytest.mark.parametrize("k", BAD)
def test_bad(k):
    e = errs(mut(BAD[k]))
    assert e and all(x.startswith("flow bugfix") for x in e)


def test_errors_never_show_values():
    secret = "xoxb-123456789-SECRETVALUE"  # noqa: S105
    e = errs(mut(lambda d: d["steps"][0].update(goal=secret, agent="BOTSECRET")))
    assert e and not any("SECRET" in x for x in e)
    e = errs(mut(lambda d: d.update(zzz="ZVAL")))
    assert e and not any("zzz" in x or "ZVAL" in x for x in e)


def test_non_mapping():
    assert errs([1]) and errs(None)


def flow():
    return parse_flow(data(), "bugfix", TAGS)


def test_flow_fields():
    f = flow()
    assert f.name == "bugfix" and f.hash == flow_hash(data())
    assert f.tags == {"reproduce", "implement", "review", "e2e", "deps"}
    assert f.description == "Fix a bug."


def test_expand_gives_template_source():
    r = expand(flow(), goal="the bug")
    assert r["source"] == f"template:bugfix@{flow().hash}"
    s = r["steps"]
    assert [x["capability"] for x in s] == [
        "tag:reproduce",
        "tag:implement",
        "tag:e2e",
        "tag:review",
    ]
    assert s[0]["goal"] == "Test the bug" and s[2]["goal"] == "Check e2e"
    assert s[1]["gate"] == "approval" and s[1]["access"] == "write"
    assert s[2]["exclude_agents_of"] == [1] and s[2]["on_fail"] == 3
    assert all(x["agent"] == "any" for x in s)


def test_expand_param_and_bad_param():
    assert expand(flow(), params={"check": "deps"})["steps"][2]["capability"] == "tag:deps"
    with pytest.raises(ValueError):
        expand(flow(), params={"check": "zzz"})


def test_matches():
    f = flow()
    steps = expand(f, goal="g")["steps"]
    assert f.matches(steps, {}, "U1")
    # goal, payload, target are free
    free = copy.deepcopy(steps)
    free[0].update(goal="other", payload={"a": 1}, target="t")
    assert f.matches(free, {}, "U1")
    # param value is allowed
    assert f.matches(expand(f, params={"check": "deps"})["steps"], {}, "U1")

    def changed(fn):
        s = copy.deepcopy(steps)
        fn(s)
        return not f.matches(s, {}, "U1")

    assert changed(lambda s: s.pop())
    assert changed(lambda s: s.append(dict(s[-1])))
    assert changed(lambda s: s[0].update(capability="tag:review"))
    assert changed(lambda s: s[0].update(access="write"))
    assert changed(lambda s: s.reverse())
    assert changed(lambda s: s[1].pop("gate"))
    assert changed(lambda s: s[2].pop("on_fail"))
    assert changed(lambda s: s[2].update(exclude_agents_of=[0]))
    assert changed(lambda s: s[2].update(capability="tag:implement"))
    assert changed(lambda s: s[0].update(agent="B1"))
    assert not f.matches("junk", {}, "U1")


def test_matches_accepts_step_objects():
    from pipe.core.pipeline import Step

    f = flow()
    steps = [
        Step(
            x["agent"],
            x["access"],
            x["goal"],
            x["capability"],
            None,
            None,
            tuple(x["exclude_agents_of"]) if "exclude_agents_of" in x else None,
            x.get("gate"),
            x.get("on_fail"),
        )
        for x in expand(f)["steps"]
    ]
    assert f.matches(steps, {}, "U1")


def human_data():
    d = data()
    del d["steps"][2]["on_fail"], d["steps"][3]
    d["steps"].append({"id": "ok", "agent": "$starter", "access": "approve", "goal": "Approve"})
    return d


def test_human_step():
    f = parse_flow(human_data(), "bugfix", TAGS)
    steps = expand(f, starter="U1")["steps"]
    assert steps[-1]["agent"] == "human:U1" and "capability" not in steps[-1]
    assert f.matches(steps, {}, "U1") and not f.matches(steps, {}, "U2")


def agent_data():
    d = data()
    d["steps"][0]["agent"] = "$agent"
    return d


def cards(tag):
    skills = [{"id": "z", "tags": [tag], "access": "read"}, {"id": "a", "tags": [tag]}]
    return {"B2": NS(skills=skills)}


def test_agent_step():
    f = parse_flow(agent_data(), "bugfix", TAGS)
    s = expand(f, agent="B2", cards=cards("reproduce"))["steps"]
    assert s[0]["agent"] == "B2" and s[0]["capability"] == "a"
    assert f.matches(s, cards("reproduce"), "U1")
    assert not f.matches(s, cards("other"), "U1")
    assert not f.matches(s, {}, "U1")


def test_effective_source_with_real_flow():
    f = flow()
    r = expand(f)
    plan = NS(source=r["source"], steps=r["steps"])
    assert effective_source(plan, {"bugfix": f}, {}, "U1") == "template"
    plan.source = "template:bugfix@" + "0" * 32
    assert effective_source(plan, {"bugfix": f}, {}, "U1") == "free"
    assert effective_source(plan, {}, {}, "U1") == "free"
