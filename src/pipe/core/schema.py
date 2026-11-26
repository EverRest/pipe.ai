"""Stdlib validator for a small JSON Schema subset. Pure."""

import json

TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
KEYS = {"type", "properties", "required", "items", "enum", "minLength", "maxLength"}
KEYS |= {"minimum", "maximum", "additionalProperties", "title", "description"}
_PY = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def check_schema(schema, _depth=1) -> list[str]:
    """Errors for anything outside the subset."""
    if _depth == 1 and len(json.dumps(schema, sort_keys=True, separators=(",", ":"))) > 2000:
        return ["schema too long"]
    if not isinstance(schema, dict):
        return ["schema must be an object"]
    if _depth > 5:
        return ["schema too deep"]
    errs = [f"unsupported keyword: {k}" for k in schema if k not in KEYS]
    if "type" in schema and schema["type"] not in TYPES:
        errs.append("bad type")
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        errs.append("additionalProperties must be boolean")
    props = schema.get("properties")
    subs = list(props.values()) if isinstance(props, dict) else []
    if "items" in schema:
        subs.append(schema["items"])
    for s in subs:
        errs += check_schema(s, _depth + 1)
    return errs


def _ok(v, t):
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _PY[t]) and (t == "boolean" or not isinstance(v, bool))


def validate_schema(instance, schema, path="payload") -> list[str]:
    """Error sentences with the path only, never the value."""
    t = schema.get("type")
    if t and not _ok(instance, t):
        return [f"{path}: expected {t}"]
    errs = []
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: not in enum")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errs.append(f"{path}: too short")
        if len(instance) > schema.get("maxLength", len(instance)):
            errs.append(f"{path}: too long")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if instance < schema.get("minimum", instance):
            errs.append(f"{path}: below minimum")
        if instance > schema.get("maximum", instance):
            errs.append(f"{path}: above maximum")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        errs += [f"{path}.{k}: missing" for k in schema.get("required", []) if k not in instance]
        if schema.get("additionalProperties") is False and set(instance) - set(props):
            errs.append(f"{path}: unexpected key")
        for k, s in props.items():
            if k in instance:
                errs += validate_schema(instance[k], s, f"{path}.{k}")
    if isinstance(instance, list) and "items" in schema:
        for i, v in enumerate(instance):
            errs += validate_schema(v, schema["items"], f"{path}[{i}]")
    return errs
