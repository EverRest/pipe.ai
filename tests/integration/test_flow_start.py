"""Start a flow by name (SC-001 to SC-003). No LLM call on the `flow:` path."""

from flow_kit import FlowRig, meta


def test_flow_word_plans_with_no_runtime_call_and_check_starts_it():
    r = FlowRig()
    r.say("<@UA> flow:bugfix the login page crashes")
    plan = r.plan()
    p = meta(plan)
    assert p["status"] == "needs_approval" and p["pipeline"]["source"].startswith(
        "template:bugfix@"
    )
    assert "the login page crashes" in p["pipeline"]["steps"][0]["goal"]
    assert all(not rt.inputs for rt in r.rt.values()) and not r.task(phase="step")
    r.react(plan, "U8")  # not the starter, not the owner
    assert not r.task(phase="step") and len(r.task("B1", "plan")) == 1
    r.react(plan, "U9")
    assert meta(r.task("B1", "plan")[-1])["status"] == "done"
    assert len(r.task("B1", "plan")) == 2


def test_override_wins(tmp_path):
    from flow_kit import FLOWS, TAGS
    from pipe.flows_io import load_flows

    (tmp_path / "bugfix.yaml").write_text(
        "name: bugfix\nversion: 1\ndescription: mine\nsteps:\n"
        "  - {id: a, agent: any, capability: 'tag:review', goal: 'look {goal}'}\n"
    )
    r = FlowRig(flows=load_flows(FLOWS, tmp_path, TAGS))
    r.say("<@UA> flow:bugfix x")
    assert [s["capability"] for s in meta(r.plan())["pipeline"]["steps"]] == ["tag:review"]


def test_unknown_name_lists_known_flows():
    r = FlowRig()
    top = r.say("<@UA> flow:nope x")
    (m,) = [p for p in r.posts() if p["thread"] == top.ts]
    assert "flow nope not found" in m["text"] and "bugfix" in m["text"] and not m["metadata"]


def test_missing_tags_are_named_and_nothing_starts():
    offers = {"B1": ["decompose", "implement"], "B2": ["decompose", "implement"], "B3": []}
    r = FlowRig(offers=offers)
    top = r.say("<@UA> flow:feature-dev x")
    (m,) = [p for p in r.posts() if p["thread"] == top.ts]
    assert "flow feature-dev: missing tags: e2e, review" in m["text"]
    assert not r.task(phase="plan")


def test_bad_parameter_and_agent_rules():
    r = FlowRig()
    top = r.say("<@UA> flow:nightly check=lint x")
    assert (
        "flow nightly: bad value for check"
        in [p for p in r.posts() if p["thread"] == top.ts][-1]["text"]
    )
    top = r.say("<@UA> <@UB> flow:bugfix x")
    assert "takes no agent mention" in [p for p in r.posts() if p["thread"] == top.ts][-1]["text"]
    top = r.say("<@UA> flow:delegate x")
    assert (
        "needs a second agent mention"
        in [p for p in r.posts() if p["thread"] == top.ts][-1]["text"]
    )


def test_one_agent_and_flow_word_is_a_pipeline_request_but_a_reply_is_chat():
    r = FlowRig()
    top = r.say("<@UA> flow:research x")
    assert len(r.task("B1", "plan")) == 1
    r.reply(top, "<@UA> flow:bugfix y")
    assert len(r.task("B1", "plan")) == 1


def test_free_text_flow_output_expands_the_template_and_ignores_steps():
    r = FlowRig()
    r.rt["B1"].plan_out = {"flow": "bugfix", "steps": [{"agent": "B1"}], "source": "free"}
    r.say("<@UA> <@UB> fix the login bug")
    p = meta(r.plan())["pipeline"]
    assert p["source"].startswith("template:bugfix@") and len(p["steps"]) == 5
    assert len([i for i in r.rt["B1"].inputs if i.task["purpose"] == "plan"]) == 1
    assert "fix the login bug" in p["steps"][0]["goal"]


def test_free_text_unknown_flow_fails():
    r = FlowRig()
    r.rt["B1"].plan_out = {"flow": "nope"}
    top = r.say("<@UA> <@UB> do things")
    assert "could not build a plan" in [p for p in r.posts() if p["thread"] == top.ts][-1]["text"]


def test_save_as_flow_writes_no_file(pipe_home):
    r = FlowRig()
    r.say("<@UA> save this as a flow")
    assert not list((pipe_home / "flows").glob("*")) if (pipe_home / "flows").exists() else True
