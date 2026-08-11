from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis

from job_pilot.core.cache import CacheStore, DistributedLock, RedisCacheStore, RedisDistributedLock
from job_pilot.core.config import Settings
from job_pilot.core.exceptions import ResourceUnavailableError
from job_pilot.core.search import SearchBackend, SqlLikeSearchBackend
from job_pilot.db.session import DatabaseResource, build_database_resource

# TODO: 第七阶段处理 MQ ES


class HealthCheckable(Protocol):
    async def health_check(self) -> bool: ...


@dataclass(slots=True, frozen=True)
class ResourceSpec:
    """进程资源声明，用于按需构建当前进程真正需要的连接资源。"""

    database: bool = True
    redis: bool = True
    cache: bool = True
    lock: bool = True
    search: bool = True


@dataclass(slots=True)
class AppResources:
    """应用/worker 进程持有的资源容器。

    不同进程可以只构建自己需要的资源；业务入口通过 require_* 获取强类型资源。
    """

    database: DatabaseResource | None = None
    cache: CacheStore | None = None
    lock: DistributedLock | None = None
    redis_client: Redis | None = None
    search_backend: SearchBackend | None = None

    async def health_check(self) -> dict[str, bool]:
        result: dict[str, bool] = {}

        if self.database is not None:
            result["database"] = await self._check_health(self.database)
        if self.redis_client is not None:
            result["redis"] = await self._check_redis(self.redis_client)
        if self.search_backend is not None:
            result["search_backend"] = await self._check_health(self.search_backend)
        return result

    async def close(self) -> None:
        if self.redis_client is not None:
            await self.redis_client.aclose()
        if self.search_backend is not None:
            await self.search_backend.close()
        if self.database is not None:
            await self.database.close()

    def require_database(self) -> DatabaseResource:
        if self.database is None:
            raise ResourceUnavailableError(
                "Database resource is not configured",
                code="DATABASE_RESOURCE_UNAVAILABLE",
            )
        return self.database

    def require_cache(self) -> CacheStore:
        if self.cache is None:
            raise ResourceUnavailableError(
                "Cache resource is not configured",
                code="CACHE_RESOURCE_UNAVAILABLE",
            )
        return self.cache

    def require_lock(self) -> DistributedLock:
        if self.lock is None:
            raise ResourceUnavailableError(
                "Distributed lock resource is not configured",
                code="LOCK_RESOURCE_UNAVAILABLE",
            )
        return self.lock

    def require_redis_client(self) -> Redis:
        if self.redis_client is None:
            raise ResourceUnavailableError(
                "Redis resource is not configured",
                code="REDIS_RESOURCE_UNAVAILABLE",
            )
        return self.redis_client

    def require_search_backend(self) -> SearchBackend:
        if self.search_backend is None:
            raise ResourceUnavailableError(
                "SearchBackend resource is not configured",
                code="SEARCHBACKEND_RESOURCE_UNAVAILABLE",
            )
        return self.search_backend

    @staticmethod
    async def _check_redis(redis_client: Redis) -> bool:
        try:
            return bool(await redis_client.ping())
        except Exception:
            return False

    @staticmethod
    async def _check_health(resource: HealthCheckable) -> bool:
        try:
            return await resource.health_check()
        except Exception:
            return False


def build_app_resources(
    settings: Settings,
    *,
    spec: ResourceSpec | None = None,
) -> AppResources:
    """按资源声明构建进程资源，默认构建 FastAPI 所需的完整资源。"""

    selected_spec = spec or ResourceSpec()

    database = build_database_resource(settings) if selected_spec.database else None

    redis_needed = selected_spec.redis or selected_spec.cache or selected_spec.lock
    redis_client = (
        Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        if redis_needed
        else None
    )

    cache: CacheStore | None = None
    if selected_spec.cache:
        redis_for_cache = _require_built_redis(redis_client, "cache")
        cache = RedisCacheStore(redis_for_cache)

    lock: DistributedLock | None = None
    if selected_spec.lock:
        redis_for_lock = _require_built_redis(redis_client, "lock")
        lock = RedisDistributedLock(redis_for_lock)

    # TODO: 待处理完善，阶段 7
    search_backend = SqlLikeSearchBackend() if selected_spec.search else None
    return AppResources(
        database=database,
        cache=cache,
        lock=lock,
        redis_client=redis_client,
        search_backend=search_backend,
    )


def build_database_only_resources(settings: Settings) -> AppResources:
    """构建只需要数据库的脚本/worker 资源。"""

    return build_app_resources(
        settings,
        spec=ResourceSpec(
            redis=False,
            cache=False,
            lock=False,
            search=False,
        ),
    )


def _require_built_redis(redis_client: Redis | None, resource_name: str) -> Redis:
    if redis_client is None:
        raise ResourceUnavailableError(
            f"Redis resource is required to build {resource_name}",
            code="REDIS_RESOURCE_REQUIRED",
        )
    return redis_client
