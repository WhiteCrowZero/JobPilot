from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("APP_ENV", "test")

from job_pilot.core.config import settings  # noqa: E402
from job_pilot.core.resources import AppResources, build_app_resources  # noqa: E402
from job_pilot.main import create_app  # noqa: E402


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


async def truncate_auth_user_tables(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                auth_password_credentials,
                auth_identities,
                user_profiles,
                users
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()


@pytest_asyncio.fixture
async def app_resources() -> AsyncIterator[AppResources]:
    resources = build_app_resources(settings)
    try:
        yield resources
    finally:
        await resources.close()


@pytest_asyncio.fixture
async def db_session(app_resources: AppResources) -> AsyncIterator[AsyncSession]:
    async with app_resources.require_database().session_factory() as session:
        await truncate_auth_user_tables(session)
        try:
            yield session
        finally:
            await session.rollback()
            await truncate_auth_user_tables(session)


@pytest_asyncio.fixture
async def test_app(app_resources: AppResources) -> FastAPI:
    app = create_app()
    app.state.resources = app_resources
    return app


@pytest_asyncio.fixture
async def api_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[httpx.AsyncClient]:
    _ = db_session
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
