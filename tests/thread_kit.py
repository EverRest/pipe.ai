"""Builders for route and stepper tests: cards, task messages, thread state."""

from pipe.core.contract import Message
from pipe.core.route import ThreadState

TOP = "1700000000.000001"
CARDS = {
    "B1": {
        "bot_id": "B1",
        "bot_user_id": "UA",
        "owner": "OA",
        "name": "agent-a",
        "skills": [{"id": "cap-1", "tags": ["review"]}],
    },
    "B2": {
        "bot_id": "B2",
        "bot_user_id": "UB",
        "owner": "OB",
        "name": "agent-b",
        "skills": [{"id": "cap-2", "tags": ["review"]}],
    },
    "B3": {
        "bot_id": "B3",
        "bot_user_id": "UC",
        "owner": "OC",
        "name": "agent-c",
        "skills": [{"id": "cap-3"}],
    },
}
USERS = {c["bot_user_id"]: k for k, c in CARDS.items()}
PARENT = "<@UA> do it with <@UB>"


def step(agent="B1", cap="cap-1", **kw):
    return {"agent": agent, "capability": cap, "access": "read", "goal": "do it", **kw}


def human(user="U9"):
    return {"agent": f"human:{user}", "access": "approve", "goal": "ok?"}


PLAN = {"steps": [step("B1", "cap-1"), step("B2", "cap-2")], "source": "free"}


def ts(n):
    return f"1700000{n:03d}.000000"


def task(n, sender, phase="step", status="done", hop=1, **kw):
    """A trusted-looking task message at time n. kw go into the payload; `text` sets the text."""
    text = kw.pop("text", "")
    p = {"v": 1, "task_id": TOP, "phase": phase, "status": status, "by": sender, "hop": hop}
    p.update(kw)
    meta = {"event_type": "pipe.task.v1", "event_payload": p}
    handle = CARDS[sender]["bot_user_id"] if sender in CARDS else None
    return Message("C", ts(n), TOP, sender, True, text, handle, meta)


def plan_msg(n=1, by="B1", plan=PLAN, status="needs_approval", **kw):
    return task(n, by, "plan", status, 0, pipeline=plan, step=0, **kw)


def start_msg(n=2, by="B1", agent="B1", i=0):
    nxt = {"agent": agent, "access": "read", "payload": {"step": i}}
    return task(n, by, "plan", "done", 1, step=0, next=nxt)


def handoff(n, by, to, i, src, hop, text=""):
    nxt = {"agent": to, "access": "read", "payload": {"step": i}}
    return task(
        n, by, "step", "done", hop, step=src, access="read", next=nxt, artifacts=[], text=text
    )


def claim(n, by, i, status="claimed", hop=1, **kw):
    return task(n, by, "step", status, hop, step=i, access="read", **kw)


def state(msgs=(), me="B1", starter="U9", parent=PARENT, **kw):
    parent_msg = Message("C", TOP, TOP, starter or "U9", False, parent)
    return ThreadState(
        "C",
        TOP,
        starter,
        parent,
        (parent_msg, *msgs),
        CARDS,
        USERS,
        me,
        CARDS[me]["bot_user_id"],
        **kw,
    )
