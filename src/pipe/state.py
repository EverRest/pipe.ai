"""Local state files under PIPE_HOME (default ~/.pipe)."""

import json
import os
import re
import tempfile
from pathlib import Path

CAP = 500


def pipe_home() -> Path:
    return Path(os.environ.get("PIPE_HOME") or "~/.pipe").expanduser()


def atomic_write(path: Path, data: dict) -> None:
    """Write JSON to a temp file (mode 0600), then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read(path: Path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def load_state() -> dict:
    return _read(pipe_home() / "state.json", {})


def save_state(**updates) -> None:
    """Merge keys into state.json (also bot_id, agents_channel_id, card, summary_hash).

    last_seen_ts moves forward only.
    """
    st = load_state()
    new = updates.get("last_seen_ts")
    if new is not None and float(new) <= float(st.get("last_seen_ts") or 0):
        updates.pop("last_seen_ts")
    atomic_write(pipe_home() / "state.json", {**st, **updates})


def init_last_seen(now_ts: str) -> None:
    """First start: no old history is answered (A6)."""
    if "last_seen_ts" not in load_state():
        save_state(last_seen_ts=now_ts)


def load_seen() -> dict:
    s = _read(pipe_home() / "seen.json", {})
    return {"event_ids": s.get("event_ids", []), "mention_keys": s.get("mention_keys", [])}


def save_seen(event_ids: list[str], mention_keys: list[str]) -> None:
    atomic_write(
        pipe_home() / "seen.json",
        {"event_ids": event_ids[-CAP:], "mention_keys": mention_keys[-CAP:]},
    )


def _session_path(session_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        raise ValueError("invalid session_id")
    return pipe_home() / "status" / f"{session_id}.json"


def load_session(session_id: str) -> dict | None:
    return _read(_session_path(session_id), None)


def save_session(session_id: str, data: dict) -> None:
    atomic_write(_session_path(session_id), data)
