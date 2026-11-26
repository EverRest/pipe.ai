.PHONY: lint format test ci hooks

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

test:
	.venv/bin/pytest -q

ci: lint test

hooks:
	pre-commit install
