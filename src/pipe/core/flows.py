"""Flow templates: check, hash, expand, shape match. Pure, no I/O."""

import hashlib
import json
import re
from dataclasses import dataclass

from pipe.core.pipeline import access_fits, matches_tag
from pipe.core.route import mentions
from pipe.core.scrub import scrub
from pipe.core.source import MAX_HOP_TEMPLATE

_ID = re.compile(r"[a-z0-9-]{1,32}")
_KEY = re.compile(r"[a-z]{1,16}")
_CAP = re.compile(r"tag:(?:([a-z0-9-]{1,32})|\$([a-z]{1,16}))")
_TOP = {"name", "version", "description", "params", "steps"}
_STEP = {
    "id",
    "agent",
    "capability",
    "access",
    "goal",
    "payload",
    "gate",
    "exclude_agents_of",
    "on_fail",
}
_BAD_TEXT = ("://", "/Users/", "/home/", "~/")


def flow_hash(data) -> str:
    """32 hex chars of sha256 over the canonical JSON of the parsed mapping."""
    j = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(j.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class Flow:
    name: str
    hash: str
    description: str
    steps: tuple  # normalized step dicts, ids resolved to indexes
    tags: frozenset  # every tag the flow can use
    params: dict
    origin: str = ""

    def matches(self, steps, cards, starter) -> bool:
        """The plan steps equal the expanded template. goal, payload, target are free."""
        try:
            return self._matches(steps, cards or {}, starter)
        except Exception:
            return False

    def _matches(self, steps, cards, starter) -> bool:
        steps = [s if isinstance(s, dict) else vars(s) for s in steps]
        if len(steps) != len(self.steps):
            return False
        for p, t in zip(steps, self.steps, strict=True):
            same = all(
                _norm(p.get(k)) == _norm(t[k])
                for k in ("access", "gate", "on_fail", "exclude_agents_of")
            )
            if not same:
                return False
            cap, agent = p.get("capability"), p.get("agent")
            if t["kind"] == "human":
                ok = agent == f"human:{starter}" and cap is None
            else:
                tag = cap[4:] if t["kind"] == "any" and isinstance(cap, str) else None
                if t["kind"] == "any":
                    ok = agent == "any" and tag in t["tags"] and cap == f"tag:{tag}"
                else:
                    ok = _agent_ok(cards.get(agent), cap, t)
            if not ok:
                return False
        return True


def _norm(v):
    return tuple(v) if isinstance(v, (list, tuple)) else v


def _agent_ok(card, cap, t) -> bool:
    entry = next((e for e in getattr(card, "skills", ()) if e.get("id") == cap), None)
    return (
        entry is not None
        and bool(set(entry.get("tags") or ()) & set(t["tags"]))
        and access_fits(t["access"], entry.get("access"))
    )


def validate_flow(data, stem, tags) -> list[str]:
    """Errors of a parsed template. `tags` maps tag -> default access.

    Messages name the template and the field, never a value.
    """
    return _check(data, stem, tags)[0]


def _check(data, stem, tags):
    errs, out = [], []
    p = f"flow {stem}"
    err = lambda m: errs.append(f"{p}: {m}")  # noqa: E731
    if not isinstance(data, dict):
        return [f"{p}: not a mapping"], out
    if data.keys() - _TOP:
        err("unknown top-level key")
    if data.get("version") != 1:
        err("version must be 1")
    name = data.get("name")
    if not (isinstance(name, str) and _ID.fullmatch(name) and name == stem):
        err("name must match the file name")
    desc = data.get("description")
    if not (isinstance(desc, str) and 1 <= len(desc) <= 200):
        err("description must have 1 to 200 characters")
    params = data.get("params", {})
    if not isinstance(params, dict):
        err("params must be a mapping")
        params = {}
    for k, v in params.items():
        vals = v.get("values") if isinstance(v, dict) else None
        ok = (
            isinstance(k, str)
            and _KEY.fullmatch(k)
            and isinstance(vals, list)
            and 2 <= len(vals) <= 8
            and all(isinstance(x, str) and x in tags for x in vals)
            and v.get("default") in vals
            and v.keys() <= {"values", "default"}
        )
        if not ok:
            err("a param is invalid")
            params = {}
            break
    steps = data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 6:
        err("steps must be a list of 1 to 6")
        return errs, out
    ids = [s.get("id") if isinstance(s, dict) else None for s in steps]
    used, agents, humans, with_agent = set(), 0, 0, 0
    for i, s in enumerate(steps):
        e = lambda m, i=i: err(f"step {i + 1}: {m}")  # noqa: E731
        if not isinstance(s, dict):
            e("not a mapping")
            continue
        if s.keys() - _STEP:
            e("unknown key")
        if not (isinstance(ids[i], str) and _ID.fullmatch(ids[i])) or ids.count(ids[i]) > 1:
            e("id must be unique and match the pattern")
        goal = s.get("goal")
        if not (isinstance(goal, str) and 1 <= len(goal) <= 300):
            e("goal must have 1 to 300 characters")
        else:
            rest = re.sub(
                r"\{(\w+)\}", lambda m: "" if m[1] == "goal" or m[1] in params else "{", goal
            )
            if "{" in rest or "}" in rest or "$" in rest:
                e("goal has an unknown placeholder")
            used |= {m for m in re.findall(r"\{(\w+)\}", goal)}
        pl = s.get("payload")
        if pl is not None:
            try:
                bad = not isinstance(pl, dict) or len(json.dumps(pl)) > 500
            except TypeError, ValueError:
                bad = True
            if bad:
                e("payload must be a small mapping")
        if s.get("gate") not in (None, "approval"):
            e("gate must be approval")
        agent, cap, acc = s.get("agent"), s.get("capability"), s.get("access")
        t = {"gate": s.get("gate"), "goal": goal, "payload": pl, "id": ids[i]}
        if agent == "$starter":
            humans += 1
            if cap is not None or acc != "approve" or i != len(steps) - 1:
                e("human step must be last, with access approve and no capability")
            if pl is not None or s.keys() & {"gate", "on_fail", "exclude_agents_of"}:
                e("human step has a forbidden field")
            t |= {"kind": "human", "tags": (), "access": "approve"}
        else:
            agents += 1
            if agent not in ("any", "$agent"):
                e("agent must be any or $agent")
            with_agent += agent == "$agent"
            m = _CAP.fullmatch(cap) if isinstance(cap, str) else None
            if not m:
                e("capability must be tag:<tag> or tag:$<param>")
                continue
            if m[2]:
                used.add(m[2])
                vals = params.get(m[2], {}).get("values", ())
                if not vals:
                    e("capability names an unknown param")
            else:
                vals = (m[1],)
                if m[1] not in tags:
                    e("capability tag is not in the vocabulary")
            accs = {tags[v] for v in vals if v in tags}
            if len(accs) != 1:
                e("tags of the capability need one default access")
                continue
            default = accs.pop()
            if acc not in (None, default):
                e("access differs from the tag default")
            t |= {
                "kind": "any" if agent == "any" else "agent",
                "tags": tuple(vals),
                "access": default,
            }
            t["param"] = m[2]
        out.append(t)
        _walk_text(s, lambda m, e=e: e(m))
    if humans > 1 or agents > MAX_HOP_TEMPLATE:
        err("too many human or agent steps")
    if with_agent > 1:
        err("at most one step may use $agent")
    if set(params) - used:
        err("a param is not used")
    _walk_text(desc, err)
    _walk_text(params, err)
    _links(steps, ids, out, err)
    return errs, out


def _walk_text(v, report):
    """Report a URL, an absolute path, or a token anywhere in `v` (value never shown)."""
    if isinstance(v, str):
        if any(b in v for b in _BAD_TEXT) or scrub(v) != v:
            report("text has a URL, a path, or a token")
    elif isinstance(v, dict):
        for k, x in v.items():
            _walk_text(k, report)
            _walk_text(x, report)
    elif isinstance(v, (list, tuple)):
        for x in v:
            _walk_text(x, report)


def _links(steps, ids, out, err):
    """Resolve exclude_agents_of and on_fail ids to indexes. Check the branch rules."""
    if len(out) != len(steps):
        return
    last = len(steps) - 1
    fails = [i for i, s in enumerate(steps) if s.get("on_fail") is not None]
    if fails and (
        len(fails) > 1
        or steps[fails[0]]["on_fail"] != ids[last]
        or fails[0] == last
        or out[last]["kind"] == "human"
        or any(t["kind"] == "human" for t in out)
    ):
        err("on_fail must be one branch to the last agent step, with no human step")
    for i, s in enumerate(steps):
        ex = s.get("exclude_agents_of")
        if ex is not None:
            ok = isinstance(ex, list) and all(
                x in ids[:i] and out[ids.index(x)]["kind"] != "human" for x in ex
            )
            if not ok:
                err(f"step {i + 1}: exclude_agents_of must name earlier agent steps")
        ok = isinstance(ex, list) and all(x in ids for x in ex)
        out[i]["exclude_agents_of"] = [ids.index(x) for x in ex] if ex and ok else None
        out[i]["on_fail"] = last if fails and i == fails[0] else None


def parse_flow(data, stem, tags, origin="") -> Flow:
    """A valid template as a Flow. Raises ValueError (with the errors) when invalid."""
    errs, steps = _check(data, stem, tags)
    if errs:
        raise ValueError("; ".join(errs))
    used = frozenset(t for s in steps for t in s["tags"])
    return Flow(
        stem,
        flow_hash(data),
        data["description"],
        tuple(steps),
        used,
        data.get("params", {}),
        origin,
    )


def expand(flow, goal="", params=None, starter=None, agent=None, cards=None) -> dict:
    """The plan steps and the `template:<name>@<hash>` source. Raises ValueError on bad input."""
    vals = {k: v["default"] for k, v in flow.params.items()}
    for k, v in (params or {}).items():
        if k not in flow.params:
            raise ValueError(f"flow {flow.name}: unknown parameter {k}")
        if v not in flow.params[k]["values"]:
            raise ValueError(f"flow {flow.name}: bad value for {k}")
        vals[k] = v
    vals["goal"] = goal
    steps = []
    for t in flow.steps:
        text = re.sub(r"\{(\w+)\}", lambda m: vals.get(m[1], m[0]), t["goal"])
        if len(text) > 500:
            raise ValueError(f"flow {flow.name}: goal too long")
        s = {"access": t["access"], "goal": text}
        if t["kind"] == "human":
            s["agent"] = f"human:{starter}"
        else:
            tag = vals[t["param"]] if t["param"] else t["tags"][0]
            s["agent"], s["capability"] = "any", f"tag:{tag}"
            if t["kind"] == "agent":
                s["agent"], s["capability"] = (
                    agent,
                    _lowest_cap((cards or {}).get(agent), tag, t, flow.name),
                )
        if t["payload"] is not None:
            s["payload"] = dict(t["payload"])
        for k in ("gate", "on_fail", "exclude_agents_of"):
            if t[k] is not None:
                s[k] = list(t[k]) if k == "exclude_agents_of" else t[k]
        steps.append(s)
    return {"steps": steps, "source": f"template:{flow.name}@{flow.hash}"}


def _lowest_cap(card, tag, t, name):
    ids = [
        e["id"]
        for e in getattr(card, "skills", ())
        if tag in (e.get("tags") or ()) and access_fits(t["access"], e.get("access"))
    ]
    if not ids:
        raise ValueError(f"flow {name}: missing tags: {tag}")
    return min(ids)


@dataclass(frozen=True)
class FlowMention:
    name: str
    params: dict
    goal: str
    agents: list


_PARAM = re.compile(r"([a-z]{1,16})=([a-z0-9-]{1,32})")


def parse_flow_mention(text, agent_users) -> FlowMention | None:
    """`flow:<name> [key=value ...] <goal>`. Agent mentions leave the goal. None without a word."""
    words = (text or "").split()
    i = next(
        (k for k, w in enumerate(words) if w.startswith("flow:") and _ID.fullmatch(w[5:])), None
    )
    if i is None:
        return None
    j, params = i + 1, {}
    while j < len(words) and (m := _PARAM.fullmatch(words[j])):
        params[m[1]] = m[2]
        j += 1
    handles = {f"<@{h}>" for h in agent_users}
    goal = " ".join(w for w in words[:i] + words[j:] if w not in handles)
    agents = list(dict.fromkeys(agent_users[h] for h in mentions(text) if h in agent_users))
    return FlowMention(words[i][5:], params, goal, agents)


def missing_tags(flow, cards, params=None, agent=None) -> list[str]:
    """Tags of the flow that no card (or the named agent's card) offers, in step order."""
    vals = {k: v["default"] for k, v in flow.params.items()} | (params or {})
    out = []
    for t in flow.steps:
        if t["kind"] == "human":
            continue
        tag = vals[t["param"]] if t["param"] else t["tags"][0]
        pool = [(cards or {}).get(agent)] if t["kind"] == "agent" else list((cards or {}).values())
        if tag not in out and not any(c and matches_tag(c, tag, t["access"]) for c in pool):
            out.append(tag)
    return out
