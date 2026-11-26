import json
import os
import stat

import pytest

from pipe import state


def mode(p):
    return stat.S_IMODE(os.stat(p).st_mode)


def test_pipe_home_override(pipe_home):
    assert state.pipe_home() == pipe_home


def test_atomic_write_mode_and_replace(pipe_home, monkeypatch):
    calls = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (calls.append((a, b)), real(a, b)))
    p = pipe_home / "x" / "f.json"
    state.atomic_write(p, {"a": 1})
    assert json.loads(p.read_text()) == {"a": 1}
    assert mode(p) == 0o600
    assert calls and calls[0][1] == p and calls[0][0] != p
    assert [f.name for f in p.parent.iterdir()] == ["f.json"]


def test_first_start_sets_last_seen(pipe_home):
    assert state.load_state() == {}
    state.init_last_seen("100.000000")
    assert state.load_state()["last_seen_ts"] == "100.000000"
    state.init_last_seen("200.000000")
    assert state.load_state()["last_seen_ts"] == "100.000000"


def test_last_seen_forward_only(pipe_home):
    state.save_state(last_seen_ts="200.000100")
    state.save_state(last_seen_ts="100.000100")
    assert state.load_state()["last_seen_ts"] == "200.000100"
    state.save_state(last_seen_ts="300.000100")
    assert state.load_state()["last_seen_ts"] == "300.000100"


def test_save_state_keeps_other_keys(pipe_home):
    state.save_state(last_seen_ts="1.0", bot_user_id="B1")
    state.save_state(status_channel_id="C1")
    assert state.load_state() == {
        "last_seen_ts": "1.0",
        "bot_user_id": "B1",
        "status_channel_id": "C1",
    }
    assert mode(pipe_home / "state.json") == 0o600


def test_seen_caps(pipe_home):
    assert state.load_seen() == {"event_ids": [], "mention_keys": []}
    ids = [f"E{i}" for i in range(600)]
    keys = [f"C:{i}" for i in range(600)]
    state.save_seen(ids, keys)
    s = state.load_seen()
    assert s["event_ids"] == ids[-500:]
    assert s["mention_keys"] == keys[-500:]
    assert mode(pipe_home / "seen.json") == 0o600


def test_session_status(pipe_home):
    assert state.load_session("s1") is None
    state.save_session("s1", {"stage": "started"})
    assert state.load_session("s1") == {"stage": "started"}
    assert mode(pipe_home / "status" / "s1.json") == 0o600


def test_session_id_rejects_traversal(pipe_home):
    for bad in ("../x", "a/b", "", "x" * 129):
        with pytest.raises(ValueError):
            state.save_session(bad, {})
        with pytest.raises(ValueError):
            state.load_session(bad)
    state.save_session("ok-1_a", {"a": 1})
    assert state.load_session("ok-1_a") == {"a": 1}
