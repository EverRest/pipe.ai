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


def render_trigger(
    name: str, status: str, reason: str | None = None, owner: str | None = None, escape=str
) -> str:
    """Status line of a trigger plan. `owner` is a ready mention: the only real one."""
    head = f"Trigger {_clean(name, escape)}: {status}."
    if owner:
        return f"{head} {owner} Accept or reject this pipeline."
    return f"{head} Reason: {_clean((reason or '')[:MAX_REASON], escape)}" if reason else head


def render_plan(steps: list, names: dict, escape=str, footer: str | None = None) -> str:
    """Plan post: one line per step. `names` maps an agent id to its card name.
    `footer` replaces the ✅ line (a trigger plan has buttons or starts at once)."""
    lines = [
        f"{i + 1}. {_clean(names.get(s['agent'], s['agent']), escape)} ({s['access']}): "
        f"{_clean(s['goal'], escape)}"
        for i, s in enumerate(steps)
    ]
    end = footer if footer is not None else "React with :white_check_mark: to start."
    return "\n".join(["Plan, needs approval:", *lines, end])
