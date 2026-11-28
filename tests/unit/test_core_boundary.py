"""Constitution XI: src/pipe/core must not name Slack, claude, git, GitLab, or wiz-review."""

import ast
from pathlib import Path

CORE = sorted((Path(__file__).resolve().parents[2] / "src/pipe/core").glob("*.py"))
BAD_MODULES = (
    "slack", "slack_sdk", "slack_bolt", "subprocess", "pipe.runtime_", "pipe.transport_",
    "pipe.git_io", "pipe.gitlab_io", "pipe.mr_gitlab", "pipe.cli", "pipe.adapter",
    "pipe.flows_io",
)  # fmt: skip
BAD_LITERALS = ("mcp__", "Bash(", "wiz", "gitlab")


def _imports(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            yield from ((a.name, n.lineno) for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            yield n.module, n.lineno


def test_core_files_found():
    assert CORE


def test_core_has_no_forbidden_imports_or_names():
    found = []
    for f in CORE:
        tree = ast.parse(f.read_text())
        found += [
            f"{f.name}:{ln} imports {m}" for m, ln in _imports(tree) if m.startswith(BAD_MODULES)
        ]
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                low = n.value.lower()
                found += [
                    f"{f.name}:{n.lineno} literal has {b}" for b in BAD_LITERALS if b.lower() in low
                ]
    assert not found, found
