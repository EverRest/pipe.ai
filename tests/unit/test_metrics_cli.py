from pipe.core.contract import Message
from pipe.metrics_cli import main

CARDS = {"BA": ("UA", "UBA"), "BB": ("UB", "UBB")}


def card(b):
    o, u = CARDS[b]
    p = {
        "name": b,
        "description": "d",
        "owner": o,
        "bot_id": b,
        "bot_user_id": u,
        "kind": "agent",
        "mode": "laptop",
        "skills": [],
        "hash": "h",
    }
    return Message(
        "CA",
        "1.0",
        "1.0",
        b,
        True,
        "c",
        sender_handle=u,
        metadata={"event_type": "pipe.card.v1", "event_payload": p},
    )


def tm(by, th, ts, status="done", phase="step", **kw):
    p = {"v": 1, "task_id": th, "phase": phase, "status": status, "by": by, "step": 0, **kw}
    return Message(
        "CW",
        ts,
        th,
        by,
        True,
        "SECRET TEXT",
        metadata={"event_type": "pipe.task.v1", "event_payload": p},
    )


MR = "https://git.example.com/g/p/-/merge_requests/1"


class Reader:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []
        self.parent = Message(
            "CW", "100.0", "100.0", "UA", False, "SECRET REQUEST", latest_reply="105.0"
        )
        self.msgs = [
            tm("BA", "100.0", "101.0", phase="plan"),
            tm("BB", "100.0", "102.0", artifacts=[MR]),
        ]

    def history(self, channel, oldest=None, limit=None):
        self.calls.append(("history", channel, oldest))
        if self.fail:
            raise OSError("slack down xoxb-123")
        return [card("BA"), card("BB")] if channel == "pipe-agents" else [self.parent]

    def replies(self, channel, thread, oldest=None):
        return [self.parent, *self.msgs]


def run(argv, gitlab, reader=None):
    out = []
    code = main(argv, reader or Reader(), gitlab, out=out.append)
    return code, "\n".join(out)


def test_prints_metrics_without_text():
    gl = lambda url: {"state": "merged", "merged_at": "2026-11-10T10:00:00Z"}  # noqa: E731
    code, out = run(["--weeks", "1"], gl)
    assert code == 0
    assert "useful delegations per week  : 1 (threshold >= 3)" in out
    assert "2026-W46: 1" in out
    assert "pipelines without manual help: 100% of 1" in out
    assert "SECRET" not in out and "git.example.com" not in out


def test_no_provider():
    code, out = run([], None)
    assert code == 0
    assert "n/a (MR state provider not configured)" in out
    assert "pipelines without manual help" in out


def test_each_mr_read_once_and_skips_counted():
    seen = []

    def gl(url):
        seen.append(url)

    r = Reader()
    r.msgs.append(tm("BB", "100.0", "103.0", artifacts=[MR]))
    _, out = run([], gl, r)
    assert seen == [MR]
    assert "skipped MR URLs: 1" in out


def test_channel_since_options_and_failure():
    r = Reader()
    run(["--channel", "CW", "--since", "2026-11-01"], None, r)
    assert ("history", "CW", "1793491200.0") in r.calls
    code, out = run([], None, Reader(fail=True))
    assert code == 1 and "xoxb" not in out
