"""Adapter start: log, card, summary (T016, T025, T037, T045, T063) and the run load."""

import logging
from pathlib import Path
from types import SimpleNamespace

from fakes import FAKE_SECRET, FAKE_URL, FakeTransport, build_claude_tree
from pipe import adapter, state
from pipe.config import Config
from pipe.core.contract import RuntimeInput
from pipe.core.runrequest import RunRequest
from pipe.core.scrub import scrub
from pipe.runtime_claude import ClaudeRuntime
from pipe.runtime_claude_load import PreparedLoad

AG = "C_AGENTS"
DECL = {
    "id": "lint",
    "runtime": "exec",
    "name": "Lint repo",
    "description": "d",
    "access": "read",
    "command": ["/bin/secret-tool"],
}


def start(tmp_path, monkeypatch, tr=None, **kw):
    home, roots = tmp_path / "home", [str(tmp_path / "repos")]
    if not home.exists():  # a second start reuses the tree
        build_claude_tree(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    tr = tr or FakeTransport(channels={"pipe-status": "C_S", "pipe-agents": AG})
    kw = {"owner": "U_OWNER", "exposed": ["skill:pa:clean"], "capabilities": [DECL]} | kw
    cfg = Config("agent", "keychain:x", repo_roots=roots, **kw)
    a = adapter.build(cfg, tr, SimpleNamespace(run=None), scrub, tr.escape_mentions)
    a.start()
    return a, tr


def test_start_posts_card_once_and_pins(tmp_path, monkeypatch):
    _, tr = start(tmp_path, monkeypatch)
    cards = [p for p in tr.posts if p["channel"] == AG]
    assert len(cards) == 1 and tr.pins[AG] == [cards[0]["ts"]]
    st = state.load_state()
    assert st["bot_id"] == "B1" and st["agents_channel_id"] == AG and st["card"]["hash"]
    start(tmp_path, monkeypatch, tr)  # second start: same card
    assert len([p for p in tr.posts if p["channel"] == AG]) == 1 and not tr.updates


def test_card_and_summary_have_no_path_url_token(tmp_path, monkeypatch):
    _, tr = start(tmp_path, monkeypatch)
    text = " ".join([*(p["text"] for p in tr.posts), *(d[1] for d in tr.dms)])
    text += str([p["metadata"] for p in tr.posts])
    for bad in (str(tmp_path), FAKE_URL, FAKE_SECRET, "/bin/secret-tool", "xox"):
        assert bad not in text


def test_summary_dm_once(tmp_path, monkeypatch):
    _, tr = start(tmp_path, monkeypatch)
    start(tmp_path, monkeypatch, tr)
    assert len(tr.dms) == 1 and tr.dms[0][0] == "U_OWNER" and state.load_state()["summary_hash"]


def test_card_failure_does_not_stop_adapter(tmp_path, monkeypatch, caplog):
    tr = FakeTransport(channels={"pipe-status": "C_S"})  # no agents channel
    caplog.set_level(logging.INFO)
    a, _ = start(tmp_path, monkeypatch, tr)
    assert tr.handlers and not tr.posts  # catch-up and handlers ran
    assert len(tr.dms) == 1  # summary is a separate step
    assert "card step failed" in caplog.text


def test_card_post_error_does_not_stop_adapter(tmp_path, monkeypatch):
    tr = FakeTransport(channels={"pipe-status": "C_S", "pipe-agents": AG})

    def boom(*a, **k):
        raise OSError("down")

    tr.post_message = boom
    start(tmp_path, monkeypatch, tr)
    assert tr.handlers and "card" not in state.load_state()


def test_summary_failure_does_not_stop_adapter(tmp_path, monkeypatch):
    tr = FakeTransport(channels={"pipe-status": "C_S", "pipe-agents": AG})
    tr.fail_dm = OSError("down")
    start(tmp_path, monkeypatch, tr)
    assert tr.handlers and "summary_hash" not in state.load_state()


def test_start_logs_list_and_notices(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    start(tmp_path, monkeypatch, exposed=["skill:pa:clean", "skill:gone"])
    log = caplog.text
    assert "skill:pa:clean" in log and "exec:lint" in log and "NOTICE unknown_id" in log
    assert FAKE_URL not in log and FAKE_SECRET not in log and str(tmp_path) not in log


# --- run load (contracts/runtime-load.md) ---------------------------------------------


class Fake:
    def __init__(self):
        self.cmds, self.dirs = [], []

    def __call__(self, argv, stdin, env, cwd, timeout):
        self.cmds.append(argv)
        return 0, '{"structured_output": {"text": "ok", "status": "done"}}'


def runtime(tmp_path, monkeypatch, fake, prep, exposed=("skill:pa:clean",)):
    home, roots = build_claude_tree(tmp_path)
    cfg = Config("a", "keychain:x", repo_roots=roots, exposed=list(exposed))
    return ClaudeRuntime(cfg, runner=fake, prepare=prep, home=home)


def inp(owner=False, ids=None):
    req = RunRequest(tuple(ids), "read", owner) if ids is not None else None
    return RuntimeInput([{"user": "u", "text": "t"}], {"id": "1"}, owner, req)


def test_run_loads_only_step_ids_and_cleans_up(tmp_path, monkeypatch):
    seen, fake = [], Fake()

    def prep(load, run_dir, entries):
        seen.append((load, Path(run_dir)))
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        return PreparedLoad(Path(run_dir) / "p", None, ["Skill"], ["Skill(pipe-exposed:clean)"])

    rt = runtime(tmp_path, monkeypatch, fake, prep, ["skill:pa:clean", "skill:mine"])
    rt.run(inp(ids=["skill:pa:clean"]))
    assert [n for n, _ in seen[0][0].skills] == ["clean"]  # `mine` is exposed, not in the step
    argv = fake.cmds[0]
    assert "--plugin-dir" in argv and "Skill" in argv[argv.index("--tools") + 1]
    assert not seen[0][1].exists()  # cleanup


def test_run_not_exposed_or_no_ids_is_stage_001(tmp_path, monkeypatch):
    fake = Fake()

    def prep(*a):
        raise AssertionError("prepare called")

    rt = runtime(tmp_path, monkeypatch, fake, prep, exposed=[])
    rt.run(inp(ids=["skill:pa:cred", "exec:lint"]))  # not exposed; declared is never loaded
    rt.run(inp(ids=[]))
    rt.run(inp())
    assert all("--plugin-dir" not in c and "--mcp-config" not in c for c in fake.cmds)


# --- SC-007: no users.info or bots.info ------------------------------------------------


class Spy:
    """Wrap a transport and record every method name that is looked up."""

    def __init__(self, inner):
        self._inner, self.names = inner, set()

    def __getattr__(self, name):
        self.names.add(name)
        return getattr(self._inner, name)


def test_publish_makes_no_user_or_bot_lookup(tmp_path, monkeypatch):
    build_claude_tree(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    spy = Spy(FakeTransport(channels={"pipe-status": "C_S", "pipe-agents": AG}))
    cfg = Config("agent", "keychain:x", owner="U_OWNER", repo_roots=[str(tmp_path / "repos")])
    a = adapter.build(cfg, spy, SimpleNamespace(run=None), scrub, spy.escape_mentions)
    a.publish_capabilities(spy.whoami())
    assert spy.names  # the spy saw calls
    assert not {n for n in spy.names if "users_info" in n or "bots_info" in n}
    assert not {n for n in spy.names if "users.info" in n or "bots.info" in n}
