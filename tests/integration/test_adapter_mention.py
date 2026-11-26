"""Ordinary mention path through Adapter with a real ClaudeRuntime (stage 001 behaviour)."""

from fakes import FakeTransport
from pipe import adapter, state
from pipe.config import Config
from pipe.core.contract import MentionEvent
from pipe.core.scrub import scrub
from pipe.runtime_claude import ClaudeRuntime

CH = "C1"


def run_mention(sender, tmp_path):
    argvs, calls = [], []

    def runner(argv, stdin, env, cwd, timeout):
        argvs.append(argv)
        return 0, '{"structured_output": {"text": "ok", "status": "done"}}'

    state.save_state(last_seen_ts="1699999999.000000")
    t = FakeTransport(channels={"pipe-status": "C_STATUS", "gen": CH, "pipe-agents": "C_AG"})
    cfg = Config("agent", "keychain:x", owner="U_OWNER", repo_roots=[str(tmp_path)])
    rt = ClaudeRuntime(
        cfg,
        runner=runner,
        prepare=lambda *a: calls.append("prepare"),
    )
    import pipe.runtime_claude as rc

    # cleanup runs in `finally` on a dir that was never made; record whether it existed
    orig = rc.cleanup
    rc.cleanup = lambda d: calls.append(("cleanup", d.exists()))
    try:
        a = adapter.build(cfg, t, rt, scrub, t.escape_mentions)
        a.start()
        m = t.add_message(CH, "<@B1> hi", sender_id=sender)
        t.raise_event(MentionEvent(CH, m.ts, m.thread, sender, False, m.text, "E1"))
    finally:
        rc.cleanup = orig
    return argvs, calls


def test_non_owner_mention_has_no_load_flags_and_no_tools(tmp_path):
    argvs, calls = run_mention("U_X", tmp_path)
    argv = argvs[0]
    assert "--plugin-dir" not in argv and "--mcp-config" not in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert all(c[0] == "cleanup" and c[1] is False for c in calls)  # no prepare, no real dir


def test_owner_mention_has_no_load_flags(tmp_path):
    argvs, calls = run_mention("U_OWNER", tmp_path)
    assert "--plugin-dir" not in argvs[0] and "--mcp-config" not in argvs[0]
    assert all(c[0] == "cleanup" and c[1] is False for c in calls)  # no prepare, no real dir
