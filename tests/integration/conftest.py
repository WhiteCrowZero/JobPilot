from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot, build_job_pilot
from job_pilot.core.config import settings
from job_pilot.core.resources import AppResources, build_app_resources
from tests.helpers.cache import MemoryCacheStore
from tests.helpers.database import truncate_auth_user_tables


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
async def pilot_resources(app_resources: AppResources) -> AsyncIterator[AppResources]:
    """构建面向库公开接口测试的资源容器。"""

    cache = MemoryCacheStore()
    resources = AppResources(
        database=app_resources.database,
        cache=cache,
    )
    try:
        yield resources
    finally:
        await cache.close()


@pytest.fixture
def pilot(pilot_resources: AppResources) -> JobPilot:
    """返回 JobPilot 公开库入口。"""

    return build_job_pilot(pilot_resources)
