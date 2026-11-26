"""One discovery pass for the CLI and the adapter: core capabilities and notices."""

from pathlib import Path

from pipe.config import Config
from pipe.core.capability import Capability, Notice
from pipe.core.exposure import exposure_notices
from pipe.declared import declared_caps
from pipe.runtime_claude_discovery import discover
from pipe.runtime_claude_exposure import to_core


def collect(cfg: Config, home: Path | None = None) -> tuple[list[Capability], list[Notice]]:
    found, skipped = discover(home or Path.home(), cfg.repo_roots)
    caps = [*map(to_core, found), *declared_caps(cfg)]
    return caps, [*skipped, *exposure_notices(caps, cfg.exposed, cfg.tags)]
