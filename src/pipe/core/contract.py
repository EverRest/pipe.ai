"""Neutral types and the runtime contract. No chat product, no tool name."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATUSES = ("done", "needs_approval", "waiting", "failed", "delegate")
REASON_MAX = 200
PROPOSAL_MAX = 4000


class RuntimeFailed(Exception):
    """A runtime run failed or its output is invalid."""


class UploadRefused(Exception):
    """upload_file refused: bad path, symlink, directory, or file over 10 MB."""


UPLOAD_MAX = 10 * 1024 * 1024


def check_upload(data: bytes | Path, roots: list[Path]) -> int:
    """Return the size of an upload, or raise UploadRefused."""
    if isinstance(data, bytes):
        size = len(data)
    else:
        p = Path(data)
        if p.is_symlink() or not p.is_file():
            raise UploadRefused("not a regular file")
        if not any(p.resolve().is_relative_to(Path(r).resolve()) for r in roots):
            raise UploadRefused("path outside the upload roots")
        size = p.stat().st_size
    if size > UPLOAD_MAX:
        raise UploadRefused("file over 10 MB")
    return size


@dataclass(frozen=True)
class Message:
    channel: str
    ts: str
    thread: str
    sender_id: str
    sender_is_bot: bool
    text: str
    sender_handle: str | None = None
    metadata: dict | None = None  # {event_type, event_payload}
    reactions: list = field(default_factory=list)  # [{name, users}]
    event_id: str | None = None
    latest_reply: str | None = None  # on parents


@dataclass(frozen=True)
class Identity:
    agent_id: str
    handle: str


@dataclass(frozen=True)
class Button:
    action_id: str
    label: str


@dataclass(frozen=True)
class MentionEvent:
    channel: str
    ts: str
    thread_ts: str
    sender_id: str
    sender_is_bot: bool
    text: str
    event_id: str | None = None


@dataclass(frozen=True)
class ReactionEvent:
    event_id: str | None
    channel: str
    item_ts: str
    sender_id: str
    name: str


@dataclass(frozen=True)
class ClickEvent:
    event_id: str | None
    channel: str
    message_ts: str
    sender_id: str
    action_id: str


@dataclass(frozen=True)
class ThreadMessage:
    user: str
    ts: str
    text: str


@dataclass(frozen=True)
class ThreadTask:
    id: str
    channel: str
    sender: str
    messages: list[ThreadMessage] = field(default_factory=list)


@dataclass(frozen=True)
class SessionStatus:
    session_id: str
    who: str
    repo: str
    branch: str
    stage: str  # started | idle | stopped
    started_at: str
    updated_at: int
    blocker: str = ""
    v: int = 1
    channel: str | None = None  # local file only
    ts: str | None = None  # local file only


@dataclass(frozen=True)
class RuntimeInput:
    thread: list[dict]  # [{user, text}]
    task: dict  # {id, purpose, ...}
    requester_is_owner: bool
    request: Any = None


@dataclass(frozen=True)
class RuntimeOutput:
    text: str
    status: str = "done"
    reason: str | None = None
    proposal: dict | None = None
    next: dict | None = None
    artifacts: list[str] = field(default_factory=list)
    data: dict | None = None


def parse_output(raw: str) -> RuntimeOutput:
    """Parse runtime JSON. Raise RuntimeFailed on any rule break."""
    try:
        d = json.loads(raw)
    except (ValueError, TypeError) as e:
        raise RuntimeFailed("output is not valid JSON") from e
    if not isinstance(d, dict):
        raise RuntimeFailed("output is not an object")
    text, status = d.get("text"), d.get("status")
    if not isinstance(text, str):
        raise RuntimeFailed("missing text")
    if status not in STATUSES:
        raise RuntimeFailed("invalid status")
    nxt, arts = d.get("next"), d.get("artifacts", [])
    if nxt is not None and not isinstance(nxt, dict):
        raise RuntimeFailed("next is not an object")
    if not isinstance(arts, list) or not all(isinstance(a, str) for a in arts):
        raise RuntimeFailed("artifacts is not a list of strings")
    data, proposal, reason = d.get("data"), d.get("proposal"), d.get("reason")
    if data is not None and not isinstance(data, dict):
        raise RuntimeFailed("data is not an object")
    if proposal is not None:
        if not isinstance(proposal, dict):
            raise RuntimeFailed("proposal is not an object")
        if len(json.dumps(proposal, sort_keys=True, separators=(",", ":"))) > PROPOSAL_MAX:
            raise RuntimeFailed("proposal too large")
    if reason is not None and not isinstance(reason, str):
        raise RuntimeFailed("reason is not a string")
    # The adapter applies scrub to text, reason, and artifacts.
    if status not in ("waiting", "failed"):
        reason = None
    elif reason is not None:
        reason = reason[:REASON_MAX]
    return RuntimeOutput(text, status, reason, proposal, nxt, arts, data)
