from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Protocol
from uuid import uuid4

from redis.asyncio import Redis

CacheValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class CacheStore(Protocol):
    """缓存抽象层"""

    async def get(self, key: str) -> CacheValue | None:
        """读取缓存。缓存不存在或缓存内容不可用时，返回 None。"""
        ...

    async def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        """写入缓存，并设置过期时间。"""
        ...

    async def take(self, key: str) -> CacheValue | None:
        """取走缓存：读取后立即删除，适合一次性 token / 临时数据。"""
        ...

    async def delete(self, key: str) -> None:
        """删除单个缓存 key。"""
        ...

    async def delete_by_prefix(self, prefix: str) -> int:
        """按前缀批量删除缓存，返回删除数量。"""
        ...

    async def close(self) -> None:
        """关闭底层连接资源。"""
        ...


class DistributedLock(Protocol):
    """分布式锁抽象层"""

    async def acquire(self, key: str, ttl_seconds: int) -> str | None:
        """尝试加锁。成功返回 token，失败返回 None。"""
        ...

    async def release(self, key: str, token: str) -> bool:
        """释放锁。只有 token 匹配时才会删除锁。"""
        ...


class RedisCacheStore:
    def __init__(
        self,
        redis_client: Redis,
        *,
        scan_count: int = 500,
        delete_batch_size: int = 500,
    ) -> None:
        self._redis: Redis = redis_client
        self._scan_count = scan_count
        self._delete_batch_size = delete_batch_size

    async def get(self, key: str) -> CacheValue | None:
        raw = await self._redis.get(key)
        return await self._decode_or_delete(key, raw)

    async def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        self._validate_ttl(ttl_seconds)
        raw = self._encode(value)
        await self._redis.set(key, raw, ex=ttl_seconds)

    async def take(self, key: str) -> CacheValue | None:
        """
        取走并删除。

        Redis 6.2+ 支持 GETDEL，可以保证“读取 + 删除”是原子操作。
        适合：
        - 一次性验证码
        - 临时 token
        - 只允许消费一次的缓存数据
        """
        raw = await self._redis.getdel(key)
        return await self._decode_or_delete(key, raw)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def delete_by_prefix(self, prefix: str) -> int:
        """
        按前缀删除缓存。

        生产注意：
        - 使用 SCAN 分批扫描；
        - 分批删除，避免一次性收集大量 key 到内存；
        - prefix 不能为空，避免误删全库。
        """
        self._validate_prefix(prefix)

        pattern = f"{prefix}*"
        batch: list[str] = []
        deleted_count = 0

        async for key in self._redis.scan_iter(
            match=pattern,
            count=self._scan_count,
        ):
            batch.append(key)

            if len(batch) >= self._delete_batch_size:
                deleted_count += await self._delete_many(batch)
                batch.clear()

        if batch:
            deleted_count += await self._delete_many(batch)

        return deleted_count

    async def close(self) -> None:
        await self._redis.aclose()

    async def _delete_many(self, keys: Sequence[str]) -> int:
        if not keys:
            return 0

        # UNLINK 是异步删除，适合删除大量 key。
        # 如果 Redis 版本不支持 UNLINK，可以退回 delete。
        try:
            result = await self._redis.unlink(*keys)
        except Exception:
            result = await self._redis.delete(*keys)

        return int(result)

    async def _decode_or_delete(self, key: str, raw: bytes | str | None) -> CacheValue | None:
        if raw is None:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 缓存内容损坏时，不应该影响主流程。
            # 直接删除坏缓存，业务层把它当缓存未命中即可。
            await self.delete(key)
            return None

    @staticmethod
    def _encode(value: CacheValue) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _validate_ttl(ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")

    @staticmethod
    def _validate_prefix(prefix: str) -> None:
        if not prefix:
            raise ValueError("prefix must not be empty")

        if prefix in {"*", ":"}:
            raise ValueError(f"unsafe cache prefix: {prefix!r}")


class RedisDistributedLock:
    _RELEASE_SCRIPT = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    end
    return 0
    """

    def __init__(self, redis_client: Redis) -> None:
        self._redis: Redis = redis_client

    async def acquire(self, key: str, ttl_seconds: int) -> str | None:
        self._validate_ttl(ttl_seconds)
        token = uuid4().hex

        acquired = await self._redis.set(
            key,
            token,
            ex=ttl_seconds,
            nx=True,
        )

        if not acquired:
            return None

        return token

    async def release(self, key: str, token: str) -> bool:
        if not token:
            return False

        result = await self._redis.eval(
            self._RELEASE_SCRIPT,
            1,
            key,
            token,
        )

        return int(result) == 1

    async def close(self) -> None:
        await self._redis.aclose()

    @staticmethod
    def _validate_ttl(ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
