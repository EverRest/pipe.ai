"""Session status and the status query. Pure."""

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime

from pipe.core.contract import Message, SessionStatus
from pipe.core.scrub import scrub

EVENT_TYPE = "pipe.status.v1"
STAGES = ("started", "idle", "stopped")
_NEXT = {"SessionStart": "started", "Stop": "idle", "SessionEnd": "stopped"}
_STR = ("session_id", "who", "repo", "branch", "stage", "blocker", "started_at")


def _ident(s: str) -> str:
    return s


def next_status(
    prev: SessionStatus | None,
    event: str,
    now: int,
    session_id: str = "",
    who: str = "",
    repo: str = "",
    branch: str = "",
) -> SessionStatus:
    """Apply a hook event. `updated_at` never moves back."""
    stage = _NEXT[event]
    if prev is None:
        iso = datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return SessionStatus(session_id, who, repo, branch, stage, iso, now)
    return replace(prev, stage=stage, updated_at=max(now, prev.updated_at))


def _fields(s: SessionStatus, escape: Callable[[str], str]) -> dict:
    t = lambda v: escape(scrub(v))  # noqa: E731
    return {
        "who": t(s.who),
        "repo": t(s.repo),
        "branch": t(s.branch),
        "stage": s.stage,
        "blocker": t(s.blocker),
    }


def _line(f: dict) -> str:
    b = f["blocker"] or "none"
    return f"{f['who']} | {f['repo']} | {f['branch']} | {f['stage']} | blocker: {b}"


def render(s: SessionStatus, escape: Callable[[str], str] = _ident) -> str:
    return _line(_fields(s, escape))


def payload(s: SessionStatus, escape: Callable[[str], str] = _ident) -> dict:
    """Message metadata `{event_type, event_payload}`. No path, token, or URL."""
    return {
        "event_type": EVENT_TYPE,
        "event_payload": {
            "v": s.v,
            "session_id": s.session_id,
            **_fields(s, escape),
            "started_at": s.started_at,
            "updated_at": s.updated_at,
        },
    }


def is_status_query(text: str, mention_text: str = "") -> bool:
    if mention_text:
        text = text.replace(mention_text, "")
    return "who works on what" in text.lower()


def parse_status_messages(messages: Iterable[Message]) -> list[SessionStatus]:
    """Keep bot-sent `pipe.status.v1` messages with valid fields. Ignore the rest."""
    out = []
    for m in messages:
        md = m.metadata or {}
        p = md.get("event_payload")
        if not m.sender_is_bot or md.get("event_type") != EVENT_TYPE or not isinstance(p, dict):
            continue
        u = p.get("updated_at")
        if not all(isinstance(p.get(k), str) for k in _STR):
            continue
        if p["stage"] not in STAGES or type(u) is not int:
            continue
        out.append(SessionStatus(*(p[k] for k in _STR[:5]), p["started_at"], u, p["blocker"]))
    return out


def recent(statuses: list[SessionStatus], now: int) -> list[SessionStatus]:
    return [s for s in statuses if s.updated_at >= now - 86400]


def render_summary(statuses: list[SessionStatus], escape: Callable[[str], str] = _ident) -> str:
    if not statuses:
        return "No sessions in the last 24 hours."
    return scrub("\n".join(render(s, escape) for s in statuses))
