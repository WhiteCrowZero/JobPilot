from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field
from redis.asyncio import Redis


class DomainEvent(BaseModel):
    """领域事件：业务已经发生的事情。"""

    event_type: str
    user_id: int
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MessageQueue(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...

    async def consume(self, timeout_seconds: int = 1) -> DomainEvent | None: ...

    async def health_check(self) -> bool: ...

    async def close(self) -> None: ...


class RedisListMessageQueue:
    """基于 Redis List 的轻量消息队列。"""

    def __init__(self, redis_url: str, queue_name: str) -> None:
        self._redis: Any = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        self._queue_name = queue_name

    async def publish(self, event: DomainEvent) -> None:
        await self._redis.lpush(self._queue_name, event.model_dump_json())

    async def consume(self, timeout_seconds: int = 1) -> DomainEvent | None:
        item = await self._redis.brpop([self._queue_name], timeout=timeout_seconds)
        if item is None:
            return None
        _, raw = item
        data = json.loads(raw)
        return DomainEvent.model_validate(data)

    async def health_check(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._redis.aclose()


class NullMessageQueue(MessageQueue):
    async def publish(self, event: DomainEvent) -> None:
        _ = event

    async def consume(self, timeout_seconds: int = 1) -> DomainEvent | None:
        _ = timeout_seconds
        return None

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        pass
