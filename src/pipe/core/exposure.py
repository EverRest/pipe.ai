"""Exposure state, list rendering, and owner notices. Pure."""

from pipe.core.capability import Capability, Notice


def exposed_by(cap: Capability, exposed) -> str | None:
    """`owner` (id or group id listed), `clean` (open item), or None."""
    if cap.role == "listed_only":
        return None
    if cap.id in exposed:
        return "owner"
    if cap.role != "item":
        return None
    if cap.group is not None and cap.group in exposed:
        return "owner"
    return "clean" if cap.open else None


def state_of(cap: Capability, exposed) -> str:
    return "exposed" if exposed_by(cap, exposed) else "owner-only"


def exposure_notices(caps: list[Capability], exposed, tag_map) -> list[Notice]:
    """`skipped` notices come from the adapter, not from here."""
    by_id = {c.id: c for c in caps}
    out = []
    for i in exposed:
        c = by_id.get(i)
        if c is None:
            out.append(Notice("unknown_id", i, f"{i} is in exposed but not discovered."))
        elif c.role == "listed_only":
            out.append(Notice("not_exposable", i, f"{i} is listed only and cannot be exposed."))
    for c in caps:
        if c.role == "item" and c.classified and not c.open and exposed_by(c, exposed) == "owner":
            out.append(
                Notice(
                    "credential_exposed",
                    c.id,
                    f"{c.id} is exposed by the owner and may use credentials.",
                )
            )
    for i in sorted(tag_map):
        if i not in by_id:
            out.append(Notice("unknown_tag_id", i, f"{i} is in tags but not discovered."))
    return out


def render_list(caps: list[Capability], exposed, notices: list[Notice]) -> list[str]:
    typ = lambda c: c.id.split(":", 1)[0]  # noqa: E731
    rows = sorted(caps, key=lambda c: (typ(c), c.id))
    if not rows:
        return ["0 capabilities"] + [f"NOTICE {n.kind}: {n.text}" for n in notices]
    states = [state_of(c, exposed) for c in rows]
    n_exp = states.count("exposed")
    out = [f"{s:<11} {typ(c):<8} {c.id:<35} {c.name}" for s, c in zip(states, rows, strict=True)]
    out += ["", f"{len(rows)} capabilities: {n_exp} exposed, {len(rows) - n_exp} owner-only."]
    return out + [f"NOTICE {n.kind}: {n.text}" for n in notices]
