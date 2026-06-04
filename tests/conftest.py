import os

import pytest

os.environ.setdefault("APP_ENV", "test")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-smoke",
        action="store_true",
        default=False,
        help="run live smoke tests against a running JobPilot service",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-smoke"):
        return

    skip_smoke = pytest.mark.skip(
        reason="smoke tests require --run-smoke and a running JobPilot service",
    )
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(skip_smoke)


@pytest.fixture
def sample_user_id() -> int:
    return 1
