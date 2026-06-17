.PHONY: sync lint format type test test-cov check clean

sync:
	uv sync --all-extras --dev

lint:
	uv run ruff check . --fix

format:
	uv run ruff format .

type:
	uv run pyright

test:
	uv run pytest

test-cov:
	uv run pytest --cov=job_pilot --cov-branch --cov-report=term-missing

clean:
	uv run python -c "import shutil, pathlib; \
[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; \
[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('.pytest_cache')]; \
[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('.ruff_cache')]; \
[pathlib.Path(p).unlink(missing_ok=True) for p in pathlib.Path('.').rglob('.coverage')]; \
[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('htmlcov')]"

check: clean format lint type test
