"""Declared (config) capabilities as core Capability values. Pure, outside core/."""

from pipe.core.capability import Capability, sanitize_tags


def declared_caps(config) -> list[Capability]:
    """Accepts a Config or its `capabilities` list. Never open: exposure is by `exposed` only."""
    entries = getattr(config, "capabilities", config)
    return [
        Capability(
            id=f"{e['runtime']}:{e['id']}",
            name=e["name"],
            description=e["description"],
            tags=(e["runtime"],),
            declared_tags=sanitize_tags(e.get("tags")),
            runtime=e["runtime"],
            access=e["access"],
            input_schema=e.get("input_schema"),
            output_schema=e.get("output_schema"),
            classified=False,
        )
        for e in entries
    ]
