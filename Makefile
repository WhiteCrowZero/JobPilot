.PHONY: install lint format type test check clean

install:
	uv sync --all-extras --dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

type:
	uv run pyright

test:
	uv run pytest

check: lint type test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
