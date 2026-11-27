"""`pipe metrics`: read `#pipe-work` and MR state, print counts and times. No database."""

import argparse
import time
from datetime import UTC, datetime

from pipe.cards import CardCache
from pipe.core.metrics import compute_metrics, render_metrics


def main(argv, reader, gitlab=None, out=print, now=time.time):
    """reader: `history`/`replies` of a Transport. gitlab: `mr_state(url)` or None."""
    ap = argparse.ArgumentParser(prog="pipe metrics")
    ap.add_argument("--channel", default="pipe-work")
    ap.add_argument("--agents-channel", default="pipe-agents")
    ap.add_argument("--weeks", type=int, default=4)
    ap.add_argument("--since", help="YYYY-MM-DD (UTC); overrides --weeks")
    a = ap.parse_args(argv)
    since = now() - a.weeks * 7 * 86400
    if a.since:
        since = datetime.fromisoformat(a.since).replace(tzinfo=UTC).timestamp()
    try:
        cards = CardCache(reader, a.agents_channel).cards()
        threads = []
        for p in reader.history(a.channel, oldest=f"{since:.1f}"):
            if p.latest_reply:
                rest = [m for m in reader.replies(a.channel, p.ts) if m.ts != p.ts]
                threads.append(sorted([p, *rest], key=lambda m: float(m.ts)))
    except Exception:  # noqa: BLE001 (never echo the error: it may hold a token)
        out("cannot read Slack")
        return 1
    states, skipped = None, 0
    if gitlab:
        states = {}
        urls = {u for t in threads for m in t for u in _urls(m)}
        for u in sorted(urls):
            s = gitlab(u)
            if s:
                states[u] = s
            else:
                skipped += 1
    out(render_metrics(compute_metrics(threads, states, cards, a.weeks)))
    if skipped:
        out(f"skipped MR URLs: {skipped}")
    return 0


def _urls(m):
    p = (m.metadata or {}).get("event_payload")
    return p.get("artifacts") or [] if isinstance(p, dict) else []
