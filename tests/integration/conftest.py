from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from job_pilot.application import JobPilot, build_job_pilot
from job_pilot.core.cache import CacheValue
from job_pilot.core.resources import AppResources


class MemoryCacheStore:
    """集成测试使用的内存缓存，避免业务测试依赖 Redis 可用性。"""

    def __init__(self) -> None:
        self.items: dict[str, CacheValue] = {}

    async def get(self, key: str) -> CacheValue | None:
        return self.items.get(key)

    async def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        _ = ttl_seconds
        self.items[key] = value

    async def take(self, key: str) -> CacheValue | None:
        return self.items.pop(key, None)

    async def delete(self, key: str) -> None:
        self.items.pop(key, None)

    async def delete_by_prefix(self, prefix: str) -> int:
        keys = [key for key in self.items if key.startswith(prefix)]
        for key in keys:
            self.items.pop(key, None)
        return len(keys)

    async def close(self) -> None:
        self.items.clear()


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
