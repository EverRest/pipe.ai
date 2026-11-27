from pipe.core.contract import Message
from pipe.core.metrics import compute_metrics, render_metrics

CARDS = {
    "BA": {"owner": "UA", "bot_user_id": "UBA"},
    "BB": {"owner": "UB", "bot_user_id": "UBB"},
}
STARTER = "UA"
_n = [0]


def tm(by, thread, status="done", step=0, phase="step", ts=None, mute=False, **extra):
    _n[0] += 1
    payload = {"v": 1, "task_id": thread, "phase": phase, "status": status, "by": by, "step": step}
    payload.update(extra)
    return Message(
        channel="C",
        ts=ts or f"{1000 + _n[0]}.0",
        thread=thread,
        sender_id=by,
        sender_is_bot=True,
        text="secret words",
        metadata={"event_type": "pipe.task.v1", "event_payload": payload},
        reactions=[{"name": "mute", "users": ["UA"]}] if mute else [],
    )


def human(thread, ts, who="UA", text="hi"):
    return Message("C", ts, thread, who, False, text)


def thread(*msgs, t="1.0"):
    return [human(t, t, STARTER, "request"), *msgs]


def start(t="1.0"):
    return tm("BA", t, phase="plan", ts="2.0", next={"agent": "BB"})


def test_delegation_counts_merged_other_owner_per_week():
    t1 = thread(start(), tm("BB", "1.0", artifacts=["https://h/a/-/merge_requests/1"]))
    t2 = thread(start(), tm("BB", "1.0", artifacts=["https://h/a/-/merge_requests/2"]))
    t3 = thread(start(), tm("BA", "1.0", artifacts=["https://h/a/-/merge_requests/3"]))
    t4 = thread(start(), tm("BB", "1.0", artifacts=["https://h/a/-/merge_requests/4"]))
    st = {
        "https://h/a/-/merge_requests/1": {"state": "merged", "merged_at": "2026-11-10T10:00:00Z"},
        "https://h/a/-/merge_requests/2": {"state": "open", "merged_at": None},
        "https://h/a/-/merge_requests/3": {"state": "merged", "merged_at": "2026-11-10T10:00:00Z"},
    }
    m = compute_metrics([t1, t2, t3, t4], st, CARDS, weeks=2)
    assert m["delegations"] == {"weeks": {"2026-W46": 1}, "per_week": 0.5}
    assert compute_metrics([t1], None, CARDS)["delegations"] is None


def test_clean_pipelines():
    done = tm("BB", "1.0", step=1)
    clean = thread(start(), tm("BB", "1.0", status="waiting", reason="owner offline"), done)
    retry = thread(start(), tm("BB", "1.0", status="failed", reason="timeout"), done)
    helped = thread(start(), done, human("1.0", "9.0", "UC"))
    approved = thread(start(), tm("BB", "1.0", status="needs_approval", phase="step"), done)
    hop = thread(start(), tm("BB", "1.0", status="failed", reason="hop limit exceeded"))
    running = thread(start(), tm("BB", "1.0", status="running"))
    m = compute_metrics([clean, retry, helped, approved, hop, running], {}, CARDS)
    assert m["clean"] == {"clean": 2, "total": 5}
    assert m["hop_stops"] == 1
    assert compute_metrics([running], {}, CARDS)["clean"] == {"clean": 0, "total": 0}


def test_dialog_answer_is_not_manual_help():
    q = tm("BB", "1.0", status="waiting", reason="needs_input", ts="3.0")
    ans = human("1.0", "9.0", "UA", "<@UBB> yes")
    t = thread(start(), q, tm("BB", "1.0", step=1), ans)
    assert compute_metrics([t], {}, CARDS)["clean"] == {"clean": 1, "total": 1}


def test_noisy_ignores_untrusted():
    rogue = Message(
        "C",
        "5.0",
        "1.0",
        "BX",
        True,
        "x",
        metadata={
            "event_type": "pipe.task.v1",
            "event_payload": {"by": "BX", "status": "done", "phase": "step"},
        },
        reactions=[{"name": "mute", "users": ["U"]}],
    )
    t = thread(start(), tm("BB", "1.0", mute=True), tm("BB", "1.0"), rogue)
    assert compute_metrics([t], {}, CARDS)["noisy"] == {"noisy": 1, "total": 3}


def test_wait_median_and_open():
    def w(wts, cts, step):
        out = [tm("BA", "1.0", status="waiting", reason="owner offline", step=step, ts=wts)]
        if cts:
            out.append(tm("BB", "1.0", status="claimed", step=step, ts=cts))
        return out

    t = thread(start(), *w("100.0", "160.0", 1), *w("200.0", "500.0", 2), *w("600.0", None, 3))
    assert compute_metrics([t], {}, CARDS)["wait"] == {"median_s": 180.0, "closed": 2, "open": 1}
    assert compute_metrics([thread(start())], {}, CARDS)["wait"] == {
        "median_s": None,
        "closed": 0,
        "open": 0,
    }


def test_render_no_text():
    t = thread(start(), tm("BB", "1.0", step=1))
    out = render_metrics(compute_metrics([t], None, CARDS))
    assert "useful delegations per week  : n/a" in out
    assert "pipelines without manual help: 100% of 1 (threshold >= 50%)" in out
    assert "ok" in out and "secret" not in out and "request" not in out
    assert out.splitlines()[-1] == "  open waits: 0"


def test_two_claims_alone_do_not_make_a_pipeline_unclean():
    claims = [tm("BB", "1.0", status="claimed", step=1, ts=f"3.{k}") for k in range(2)]
    t = thread(start(), *claims, tm("BB", "1.0", step=1))
    assert compute_metrics([t], {}, CARDS)["clean"] == {"clean": 1, "total": 1}
