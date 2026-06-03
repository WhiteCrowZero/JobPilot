from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from job_pilot.core.cache import CacheStore, DistributedLock, RedisCacheStore, RedisDistributedLock
from job_pilot.core.config import Settings
from job_pilot.core.message_queue import MessageQueue, build_message_queue


@dataclass
class AppResources:
    cache: CacheStore
    lock: DistributedLock
    message_queue: MessageQueue
    redis_client: Redis | None = None

    async def close(self) -> None:
        await self.cache.close()
        await self.message_queue.close()

        if self.redis_client is not None:
            await self.redis_client.aclose()


def build_app_resources(settings: Settings) -> AppResources:
    redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    cache: CacheStore = RedisCacheStore(redis_client)
    lock: DistributedLock = RedisDistributedLock(redis_client)
    message_queue = build_message_queue(settings)

    return AppResources(
        cache=cache,
        lock=lock,
        message_queue=message_queue,
        redis_client=redis_client,
    )
