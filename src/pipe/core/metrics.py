"""Experiment metrics (FR-023). Pure: counts and times only, no message text."""

import statistics
from collections import Counter
from datetime import datetime

TASK = "pipe.task.v1"


def _payload(m, cards):
    """Task payload of a trusted message (bot with a card, `by` equals sender), else None."""
    meta = m.metadata or {}
    p = meta.get("event_payload")
    if not (m.sender_is_bot and meta.get("event_type") == TASK and isinstance(p, dict)):
        return None
    return p if m.sender_id in cards and p.get("by") == m.sender_id else None


def _week(iso):
    y, w, _ = datetime.fromisoformat(iso).isocalendar()
    return f"{y}-W{w:02d}"


def compute_metrics(threads, mr_states, cards, weeks=4):
    """threads: message lists, parent first. mr_states: {url: {state, merged_at}} or None."""
    deleg, clean, total, noisy, agent_msgs = Counter(), 0, 0, 0, 0
    hop_stops, waits, open_waits = 0, [], 0
    for msgs in threads:
        starter = msgs[0].sender_id
        tasks = [(m, p) for m in msgs if (p := _payload(m, cards))]
        agent_msgs += len(tasks)
        noisy += sum(any(r.get("name") == "mute" for r in m.reactions) for m, _ in tasks)
        steps = [(m, p) for m, p in tasks if p.get("phase") == "step"]
        hop_stops += any(
            str(p.get("reason", "")).startswith("hop limit exceeded") for _, p in tasks
        )
        for m, p in tasks:
            for url in p.get("artifacts") or []:
                s = (mr_states or {}).get(url)
                if s and s["state"] == "merged" and cards[m.sender_id]["owner"] != starter:
                    deleg[_week(s["merged_at"])] += 1
            if p.get("status") == "waiting" and p.get("reason") == "owner offline":
                later = [
                    float(c.ts)
                    for c, q in steps
                    if q.get("step") == p.get("step")
                    and q.get("status") == "claimed"
                    and float(c.ts) > float(m.ts)
                ]
                if later:
                    waits.append(min(later) - float(m.ts))
                else:
                    open_waits += 1
        started = [
            float(m.ts) for m, p in tasks if p.get("phase") == "plan" and p["status"] == "done"
        ]
        if not started:
            continue
        done = any(p["status"] == "done" and not p.get("next") for _, p in steps)
        failed = any(p["status"] == "failed" for _, p in tasks)
        if not (done or failed):
            continue
        total += 1
        manual = any(
            not h.sender_is_bot
            and float(h.ts) > started[0]
            and not _answer(h, tasks, cards, starter)
            for h in msgs[1:]
        )
        clean += done and not failed and not manual
    return {
        "delegations": None
        if mr_states is None
        else {
            "weeks": dict(sorted(deleg.items())),
            "per_week": sum(deleg.values()) / weeks,
        },
        "clean": {"clean": clean, "total": total},
        "noisy": {"noisy": noisy, "total": agent_msgs},
        "hop_stops": hop_stops,
        "wait": {
            "median_s": statistics.median(waits) if waits else None,
            "closed": len(waits),
            "open": open_waits,
        },
    }


def _answer(h, tasks, cards, starter):
    # ponytail: needs the `needs_input` reason to stay visible in the message metadata
    return any(
        p.get("reason") == "needs_input"
        and float(m.ts) < float(h.ts)
        and h.sender_id in (cards[m.sender_id]["owner"], starter)
        and cards[m.sender_id]["bot_user_id"] in h.text
        for m, p in tasks
    )


def _pct(n, d):
    return f"{n * 100 // d}%" if d else "n/a"


def _line(label, value, thr, verdict):
    return f"{label:<29}: {value} (threshold {thr})".ljust(58) + " " + verdict


def render_metrics(m):
    d, c, n, w = m["delegations"], m["clean"], m["noisy"], m["wait"]
    out = []
    if d is None:
        out.append("useful delegations per week  : n/a (MR state provider not configured)")
    else:
        v = d["per_week"]
        out.append(
            _line("useful delegations per week", f"{v:g}", ">= 3", "ok" if v >= 3 else "below")
        )
        if d["weeks"]:
            out.append("  " + "   ".join(f"{k}: {x}" for k, x in d["weeks"].items()))
    cs = c["clean"] * 2 >= c["total"] if c["total"] else None
    out.append(
        _line(
            "pipelines without manual help",
            f"{_pct(c['clean'], c['total'])} of {c['total']}",
            ">= 50%",
            "n/a" if cs is None else "ok" if cs else "below",
        )
    )
    ns = n["noisy"] * 10 < n["total"] if n["total"] else None
    out.append(
        _line(
            "noisy agent messages",
            f"{_pct(n['noisy'], n['total'])} of {n['total']}",
            "< 10%",
            "n/a" if ns is None else "ok" if ns else "above",
        )
    )
    out.append(
        _line(
            "threads stopped by hop limit",
            m["hop_stops"],
            "0",
            "ok" if m["hop_stops"] == 0 else "above",
        )
    )
    med = "n/a" if w["median_s"] is None else f"{w['median_s'] / 60:g} min over {w['closed']} waits"
    out.append(f"{'owner offline wait, median':<29}: {med}".ljust(58) + " track")
    out.append(f"  open waits: {w['open']}")
    return "\n".join(out)
