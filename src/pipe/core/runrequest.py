"""Run request: what the core gives a runtime adapter. Pure; names no tool, flag, or runtime."""

from collections.abc import Collection
from dataclasses import dataclass


@dataclass(frozen=True)
class RunRequest:
    capabilities: tuple[str, ...]  # capability ids; empty for the planner
    access: str  # "read" (write only after spec 004)
    requester_is_owner: bool
    target: str | None = None
    payload: dict | None = None
    output_schema: dict | None = None


def planner_request() -> RunRequest:
    return RunRequest((), "read", False)


def build_run_request(
    step,
    starter: str | None,
    owner: str | None,
    output_schema: dict | None = None,
    exposed: Collection[str] | None = None,
) -> RunRequest:
    """A step loads only its own capability. `exposed` (when given) must hold it:
    an owner-only or hidden capability never loads."""
    if step.access != "read":
        raise ValueError(f"no run for access {step.access}")
    if exposed is not None and step.capability not in exposed:
        raise ValueError("capability not exposed")
    return RunRequest(
        (step.capability,),
        "read",
        bool(owner) and starter == owner,
        getattr(step, "target", None),
        step.payload,
        output_schema,
    )
