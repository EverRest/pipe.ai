"""Thread status texts. Pure. Scrub and escape every dynamic part."""

from pipe.core.scrub import scrub

MAX_REASON = 200


def _clean(s: str, escape) -> str:
    return escape(scrub(s))


def render_step(
    i: int, n: int, access: str, agent: str, status: str, reason: str | None = None, escape=str
) -> str:
    """Status line of step `i` (0-based) of `n`. Statuses: needs_approval, claimed, running,
    waiting, done, failed. `agent` is a card name or `any agent with tag <tag>`."""
    head = f"Step {i + 1} of {n} ({access}, {_clean(agent, escape)}): "
    if status == "needs_approval":
        return head + "needs approval. React with :white_check_mark: to go on."
    if reason and status in ("waiting", "failed"):
        return f"{head}{status}. Reason: {_clean(reason[:MAX_REASON], escape)}"
    return head + status


def render_stop(unverified: bool = False) -> str:
    return "Stopped. Reason: hop limit exceeded" + (
        " (plan source not verified)" if unverified else ""
    )


def render_plan(steps: list, names: dict, escape=str) -> str:
    """Plan post: one line per step. `names` maps an agent id to its card name."""
    lines = [
        f"{i + 1}. {_clean(names.get(s['agent'], s['agent']), escape)} ({s['access']}): "
        f"{_clean(s['goal'], escape)}"
        for i, s in enumerate(steps)
    ]
    return "\n".join(["Plan, needs approval:", *lines, "React with :white_check_mark: to start."])
