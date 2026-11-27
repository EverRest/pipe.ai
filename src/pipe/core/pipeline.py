"""Plan model and plan check. Pure."""

import json
import re
from dataclasses import dataclass, fields

from pipe.core.scrub import scrub
from pipe.core.source import effective_source, hop_limit, parse_source

MAX_GOAL_CHARS = 500
MAX_PAYLOAD_CHARS = 2000
_TAG = re.compile(r"tag:([a-z0-9-]{1,32})")


@dataclass(frozen=True)
class Step:
    agent: str
    access: str
    goal: str
    capability: str | None = None
    payload: dict | None = None
    target: str | None = None
    exclude_agents_of: tuple[int, ...] | None = None
    gate: str | None = None
    on_fail: int | None = None


@dataclass(frozen=True)
class Pipeline:
    steps: tuple[Step, ...]
    source: str = "free"


_STEP_FIELDS = {f.name for f in fields(Step)}


def access_fits(step_access, cap_access) -> bool:
    return cap_access is None or step_access == cap_access


def matches_tag(card, tag, access) -> bool:
    return any(
        tag in (e.get("tags") or ()) and access_fits(access, e.get("access")) for e in card.skills
    )


def _raw(plan):
    """A Pipeline or a mapping as a plain dict."""
    if isinstance(plan, Pipeline):
        steps = [{k: v for k, v in vars(s).items() if v is not None} for s in plan.steps]
        return {"steps": steps, "source": plan.source}
    return plan


def _pipeline(raw) -> Pipeline:
    """Best-effort Pipeline for the source check. effective_source never raises."""
    try:
        steps = tuple(
            Step(**{k: v for k, v in s.items() if k in _STEP_FIELDS}) for s in raw["steps"]
        )
        return Pipeline(steps, raw.get("source"))
    except Exception:
        return Pipeline((), None)


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _step_errors(i, s, n, cards, starter, prev):
    """Errors of step `i` (0-based). `prev` is the raw step before it."""
    e = []
    err = lambda m: e.append(f"step {i + 1}: {m}")  # noqa: E731
    if not isinstance(s, dict):
        return [f"step {i + 1}: not an object"]
    for k in s.keys() - _STEP_FIELDS:
        err(f"unknown field {k}")
    agent, access, cap = s.get("agent"), s.get("access"), s.get("capability")
    goal = s.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        err("goal is empty")
    elif len(goal) > MAX_GOAL_CHARS or scrub(goal) != goal:
        err(f"goal is too long or has a secret (limit {MAX_GOAL_CHARS})")
    if not isinstance(agent, str) or not agent:
        return e + [f"step {i + 1}: agent is missing"]
    if access not in ("read", "write", "approve"):
        err(f"bad access {access!r}")
    human = agent.startswith("human:")
    if human:
        user = agent[6:]
        if not user:
            err("human step has no user")
        if access != "approve":
            err("human step needs access approve")
        if cap is not None:
            err("human step has a capability")
        if s.get("payload") is not None:
            err("payload is not allowed on an approve step")
        if i == 0:
            err("the first step is a human step")
        elif i != n - 1:
            err("approve step must be the last step")
        elif user and starter is not None and user != starter:
            pa = prev.get("agent") if isinstance(prev, dict) else None
            owner = getattr(cards.get(pa), "owner", None) if isinstance(pa, str) else None
            if user != owner:
                err(f"user {user} is not the thread starter or the owner of step {i}")
    else:
        if access == "approve":
            err("bot step cannot have access approve")
        if not isinstance(cap, str) or not cap:
            err("capability is missing")
        elif agent == "any":
            m = _TAG.fullmatch(cap)
            if not m:
                err("agent any needs capability tag:<tag>")
            elif not any(matches_tag(c, m[1], access) for c in cards.values()):
                err(f"no agent offers tag {m[1]}")
        elif cap.startswith("tag:"):
            err("a tag capability needs agent any")
        else:
            card = cards.get(agent)
            entry = next((x for x in card.skills if x.get("id") == cap), None) if card else None
            if card is None:
                err(f"agent {agent} has no card")
            elif entry is None or not access_fits(access, entry.get("access")):
                err(f"capability {cap} is not available on agent {agent}")
        p = s.get("payload")
        if p is not None and (
            not isinstance(p, dict)
            or len(json.dumps(p, sort_keys=True, separators=(",", ":"), default=str))
            > MAX_PAYLOAD_CHARS
        ):
            err("payload must be an object of at most 2000 characters")
    ex, gate = s.get("exclude_agents_of"), s.get("gate")
    if ex is not None:
        bad = (
            human
            or not isinstance(ex, (list, tuple))
            or len(ex) > 5
            or len(set(map(repr, ex))) != len(ex)
            or not all(_is_int(j) and 0 <= j < i for j in ex)
        )
        if bad:
            err("bad exclude_agents_of")
    if gate is not None and (gate != "approval" or human):
        err("bad gate")
    return e


def _exclusion_errors(steps, cards):
    e = []
    for i, s in enumerate(steps):
        ex = s.get("exclude_agents_of")
        if not isinstance(ex, (list, tuple)) or not all(_is_int(j) and 0 <= j < i for j in ex):
            continue
        held = {steps[j]["agent"] for j in ex if steps[j].get("agent") != "any"}
        if s["agent"] != "any" and s["agent"] in held:
            m = 1 + next(j for j in ex if steps[j]["agent"] == s["agent"])
            e.append(f"step {i + 1}: agent {s['agent']} holds excluded step {m}")
        elif s["agent"] == "any" and (m := _TAG.fullmatch(s.get("capability") or "")):
            ok = {b for b, c in cards.items() if matches_tag(c, m[1], s.get("access"))}
            if ok and ok <= held:
                e.append(f"step {i + 1}: no agent can claim after exclusion")
    return e


def _on_fail_errors(steps):
    idx = [i for i, s in enumerate(steps) if s.get("on_fail") is not None]
    if not idx:
        return []
    last, i = len(steps) - 1, idx[0]
    ok = (
        len(idx) == 1
        and _is_int(steps[i]["on_fail"])
        and steps[i]["on_fail"] == last
        and i < last
        and not any(s["agent"].startswith("human:") for s in steps)
    )
    return [] if ok else [f"step {idx[-1] + 1}: bad on_fail"]


def validate_plan(plan, cards, starter=None, flows=None) -> list[str]:
    """Return the plan errors. An empty list means the plan is valid."""
    raw = _raw(plan)
    steps = raw.get("steps") if isinstance(raw, dict) else None
    if not isinstance(steps, (list, tuple)) or not steps:
        return ["plan has no steps"]
    n, errs = len(steps), []
    for i, s in enumerate(steps):
        errs += _step_errors(i, s, n, cards, starter, steps[i - 1] if i else {})
    if errs and not all(isinstance(s, dict) and isinstance(s.get("agent"), str) for s in steps):
        return errs
    src = raw.get("source")
    if src not in (None, "free") and parse_source(src) is None:
        errs.append("bad source")
    limit = hop_limit(effective_source(_pipeline(raw), flows, cards, starter))
    bots = sum(not s["agent"].startswith("human:") for s in steps)
    if bots > limit:
        errs.append(f"plan has {bots} agent steps, the limit is {limit}")
    return errs + _exclusion_errors(steps, cards) + _on_fail_errors(steps)
