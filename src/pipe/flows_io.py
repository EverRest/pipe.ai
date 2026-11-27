"""Load flow templates from the team dir and the owner override dir."""

from pathlib import Path

import yaml

from pipe.core.flows import parse_flow
from pipe.state import pipe_home

MAX_BYTES = 20_000


def _read(path: Path):
    """Parsed YAML of a small file. Raises ValueError (no path, no value)."""
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("file too large")
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError, UnicodeDecodeError:
        raise ValueError("not valid YAML") from None


def load_tags(path) -> dict[str, str]:
    """`flows/tags.yaml` as {tag: default access}. Empty when the file is bad."""
    try:
        t = _read(Path(path))["tags"]
        return {k: v["access"] for k, v in t.items() if v["access"] in ("read", "write")}
    except Exception:
        return {}


def load_flows(shared_dir="flows", override_dir=None, tags=None, errors=None) -> dict:
    """Valid templates by name. The override wins. A bad file is skipped.

    Errors go to the `errors` list (template name and field only).
    """
    shared = Path(shared_dir)
    tags = load_tags(shared / "tags.yaml") if tags is None else tags
    flows = {}
    for origin, d in (("git", shared), ("override", Path(override_dir or pipe_home() / "flows"))):
        for p in sorted(d.glob("*.yaml")) if d.is_dir() else ():
            if p.name == "tags.yaml" or not p.is_file():
                continue
            try:
                flows[p.stem] = parse_flow(_read(p), p.stem, tags, origin)
            except ValueError as e:
                if errors is not None:
                    errors.append(str(e) if str(e).startswith("flow ") else f"flow {p.stem}: {e}")
    return flows


def load_default(errors=None) -> dict:
    """The shipped templates plus the owner override. For the running adapter."""
    shared = Path(__file__).resolve().parents[2] / "flows"
    return load_flows(shared, None, load_tags(shared / "tags.yaml"), errors)
