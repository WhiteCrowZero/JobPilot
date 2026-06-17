from __future__ import annotations

from job_pilot.core.cache import CacheValue


class MemoryCacheStore:
    """测试使用的内存缓存，避免业务测试依赖 Redis 服务。"""

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
