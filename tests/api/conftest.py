from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.config import settings
from job_pilot.core.resources import AppResources, build_app_resources
from job_pilot.main import create_app
from tests.helpers.cache import MemoryCacheStore
from tests.helpers.database import truncate_auth_user_tables


@pytest_asyncio.fixture
async def app_resources() -> AsyncIterator[AppResources]:
    resources = build_app_resources(settings)
    cache = MemoryCacheStore()
    test_resources = AppResources(
        database=resources.database,
        cache=cache,
    )
    try:
        yield test_resources
    finally:
        await cache.close()
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
