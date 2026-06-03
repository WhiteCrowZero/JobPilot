from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from job_pilot.core.config import Settings


class DomainEvent(BaseModel):
    """领域事件：业务已经发生的事情。"""

    event_type: str
    user_id: int
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MessageQueue(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...

    async def consume(self, timeout_seconds: int = 1) -> DomainEvent | None: ...

    async def close(self) -> None: ...


class MemoryMessageQueue:
    """测试/本地学习用消息队列，只在当前 Python 进程内有效。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[DomainEvent] = asyncio.Queue()

    async def publish(self, event: DomainEvent) -> None:
        await self._queue.put(event)

    async def consume(self, timeout_seconds: int = 1) -> DomainEvent | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout_seconds)
        except TimeoutError:
            return None

    async def close(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()


class RedisListMessageQueue:
    """基于 Redis List 的轻量消息队列。"""

    def __init__(self, redis_url: str, queue_name: str) -> None:
        self._redis: Any = Redis.from_url(redis_url, decode_responses=True)
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

    async def close(self) -> None:
        await self._redis.aclose()


def build_message_queue(
    settings: Settings,
    *,
    backend: Literal["memory", "redis"] | None = None,
) -> MessageQueue:
    """Build a simple queue abstraction for future async event experiments."""

    selected_backend = backend or ("memory" if settings.is_test else "redis")
    if selected_backend == "memory":
        return MemoryMessageQueue()
    return RedisListMessageQueue(settings.REDIS_URL, queue_name="jobpilot:events")
