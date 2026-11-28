# Development

## Tests and tools

```sh
make lint    # ruff check and ruff format --check
make test    # .venv/bin/pytest -q
make ci      # lint, then test
make format  # ruff fix and format
make hooks   # pre-commit install
```

- The pre-commit hook runs `ruff check --fix` and `ruff format` with the `ruff` on `PATH`.
- `tests/unit/`: unit tests. `tests/integration/`: adapter tests with fakes.
- `tests/fakes.py` and `tests/*_kit.py`: fake transport, runtime, and helpers.
- `tests/manual/`: manual probes. `pytest` does not collect them.
- Business rules are pure functions in `src/pipe/core/`. Write the test first.

**Core is agnostic.** `src/pipe/core/` must not know Slack, `claude`, git, GitLab, wiz-review, or a tag name.
[tests/unit/test_core_boundary.py](../../tests/unit/test_core_boundary.py) checks this.

## Project layout

```text
src/pipe/           adapter, CLI, ports, transport and runtime adapters
src/pipe/core/      pure rules
flows/              flow templates and tags.yaml
templates/trigger/  CI trigger example
templates/review/   review capability example
tests/              unit, integration, manual
specs/              Spec Kit specs 001 to 008
docs/               design brief, handoff, reference, guides
```
