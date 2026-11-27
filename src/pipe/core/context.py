"""Context of earlier steps for the next step. Pure."""

MAX_CONTEXT_TEXT = 1000
MAX_CONTEXT_TOTAL = 4000


def effective_payload(step_payload, results) -> dict:
    """Plan payload plus `context` and `artifacts` of ALL earlier done steps (FR-037).
    `results` is a list of {step, text, artifacts} in step order. A plan key wins."""
    out = dict(step_payload or {})
    if not results:
        return out
    left, ctx, links = MAX_CONTEXT_TOTAL, [], []
    for r in results:
        text = (r.get("text") or "")[:MAX_CONTEXT_TEXT][: max(left, 0)]  # later texts shrink first
        left -= len(text)
        arts = list(r.get("artifacts") or ())
        ctx.append({"step": r["step"], "text": text, "artifacts": arts})
        links += [a for a in arts if a not in links]
    out.setdefault("context", ctx)
    out.setdefault("artifacts", links)
    return out
