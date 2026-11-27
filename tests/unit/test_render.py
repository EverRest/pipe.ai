from pipe.core.render import render_step, render_stop


class Fmt:
    @staticmethod
    def escape_mentions(t):
        return t.replace("<!", "&lt;!").replace("<@", "&lt;@")


def r(status, reason=None, **kw):
    return render_step(0, 3, "read", "coder-pavlo", status, reason, Fmt.escape_mentions, **kw)


def test_texts():
    assert r("claimed") == "Step 1 of 3 (read, coder-pavlo): claimed"
    assert r("running") == "Step 1 of 3 (read, coder-pavlo): running"
    assert r("done") == "Step 1 of 3 (read, coder-pavlo): done"
    assert (
        r("waiting", "owner offline")
        == "Step 1 of 3 (read, coder-pavlo): waiting. Reason: owner offline"
    )
    assert r("failed", "timeout") == "Step 1 of 3 (read, coder-pavlo): failed. Reason: timeout"
    assert r("needs_approval") == (
        "Step 1 of 3 (read, coder-pavlo): needs approval. React with :white_check_mark: to go on."
    )


def test_tag_step_and_no_claimer():
    t = render_step(1, 3, "read", "any agent with tag review", "failed", "no_claimer")
    assert t == "Step 2 of 3 (read, any agent with tag review): failed. Reason: no_claimer"


def test_scrub_escape_cut():
    assert "[redacted]" in r("failed", "bad xoxb-123-abc-def key")
    assert "<!channel>" not in r("failed", "hi <!channel>")
    assert "<@U1>" not in r("failed", "see <@U1>")
    assert len(r("failed", "x" * 500)) < 300


def test_stop():
    assert render_stop() == "Stopped. Reason: hop limit exceeded"
    assert render_stop(True) == "Stopped. Reason: hop limit exceeded (plan source not verified)"


def test_plan_text_names_agents_and_cleans_goal():
    from pipe.core.render import render_plan

    steps = [
        {"agent": "B1", "access": "read", "goal": "look <@U1>"},
        {"agent": "human:U9", "access": "approve", "goal": "ok?"},
    ]
    t = render_plan(steps, {"B1": "agent-a"}, Fmt.escape_mentions)
    assert t.splitlines()[1:3] == ["1. agent-a (read): look &lt;@U1>", "2. human:U9 (approve): ok?"]
    assert t.endswith("React with :white_check_mark: to start.")


def test_write_step():
    assert render_step(0, 2, "write", "a", "running") == "Step 1 of 2 (write, a): running"


def test_trigger_texts():
    from pipe.core.render import render_trigger

    ask = render_trigger("pipe-gitlab", "needs approval", owner="<@U_OWNER>")
    assert ask == (
        "Trigger pipe-gitlab: needs approval. <@U_OWNER> Accept or reject this pipeline."
    )
    assert render_trigger("pipe-gitlab", "failed", "rejected") == (
        "Trigger pipe-gitlab: failed. Reason: rejected"
    )
    bad = render_trigger(
        "<@U9> xoxb-123456789012", "failed", "step 2: <!channel>", escape=Fmt.escape_mentions
    )
    assert "xoxb" not in bad and "<@U9>" not in bad and "<!channel>" not in bad
