"""Runtime pick and schema checks around a step. The payload check runs before any gate."""

from pipe.core.schema import validate_schema


def pick_runtime(capability) -> str:
    return capability.runtime


def check_input(payload, schema: dict | None) -> tuple[str, list[str]] | None:
    """None if ok, else ("invalid_payload", error sentences with no value)."""
    if schema is None:
        return None
    errs = validate_schema({} if payload is None else payload, schema, "payload")
    return ("invalid_payload", errs) if errs else None


def check_output(result, schema: dict | None) -> tuple[str, list[str]] | None:
    """None if ok, else ("invalid_result", errors). `result` has `.data`."""
    if schema is None:
        return None
    if result.data is None:
        return "invalid_result", ["data: missing"]
    errs = validate_schema(result.data, schema, "data")
    return ("invalid_result", errs) if errs else None
