from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis

from job_pilot.core.cache import CacheStore, DistributedLock, RedisCacheStore, RedisDistributedLock
from job_pilot.core.config import Settings
from job_pilot.core.message_queue import MessageQueue, build_message_queue
from job_pilot.db.session import DatabaseResource, build_database_resource

"""
注意：
这里 MQ 只是简单抽象，之后还需要完善
Cache 和 Lock 暂时没问题
"""


class HealthCheckable(Protocol):
    async def health_check(self) -> bool: ...


@dataclass
class AppResources:
    database: DatabaseResource
    cache: CacheStore
    lock: DistributedLock
    redis_client: Redis
    message_queue: MessageQueue

    async def health_check(self) -> dict[str, bool]:
        return {
            "database": await self._check_health(self.database),
            "redis": await self._check_redis(),
            "message_queue": await self._check_health(self.message_queue),
        }

    async def close(self) -> None:
        await self.message_queue.close()
        await self.redis_client.aclose()
        await self.database.close()

    async def _check_redis(self) -> bool:
        try:
            return bool(await self.redis_client.ping())
        except Exception:
            return False

    @staticmethod
    async def _check_health(resource: HealthCheckable) -> bool:
        try:
            return await resource.health_check()
        except Exception:
            return False


def build_app_resources(settings: Settings) -> AppResources:
    database = build_database_resource(settings)
    redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    cache: CacheStore = RedisCacheStore(redis_client)
    lock: DistributedLock = RedisDistributedLock(redis_client)
    message_queue = build_message_queue(settings)

    return AppResources(
        database=database,
        cache=cache,
        lock=lock,
        redis_client=redis_client,
        message_queue=message_queue,
    )
