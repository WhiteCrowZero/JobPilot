from __future__ import annotations

from redis.asyncio import Redis

from job_pilot.core.config import settings

redis_client = Redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def close_redis() -> None:
    await redis_client.aclose()
