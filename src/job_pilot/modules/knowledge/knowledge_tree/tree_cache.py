from __future__ import annotations

import logging

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.cache import CacheStore
from job_pilot.modules.knowledge.knowledge_tree.tree_snapshot import KnowledgeTreeSnapshotNode
from job_pilot.modules.knowledge.models import KnowledgePoint
from job_pilot.modules.knowledge.repository import KnowledgeRepository

KNOWLEDGE_TREE_CACHE_PREFIX = "knowledge:tree:v1:"
KNOWLEDGE_TREE_CACHE_TTL_SECONDS = 60 * 60 * 3

SnapshotNodeListAdapter = TypeAdapter(list[KnowledgeTreeSnapshotNode])

logger = logging.getLogger(__name__)


class KnowledgeTreeSnapshotProvider:
    """知识点树缓存快照提供者，负责读缓存、回源和写缓存。"""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    async def get_nodes(
        self,
        db: AsyncSession,
        *,
        cache: CacheStore,
        include_archived: bool,
    ) -> list[KnowledgeTreeSnapshotNode]:
        """读取可用的扁平节点快照，缓存不可用时回源数据库。"""

        cache_key = self._build_cache_key(include_archived=include_archived)
        cached_value = await cache.get(cache_key)
        if cached_value is not None:
            try:
                return SnapshotNodeListAdapter.validate_python(cached_value)
            except ValidationError:
                logger.error(
                    "Knowledge tree cache payload was invalid",
                    extra={"cache_key": cache_key},
                )
                await cache.delete(cache_key)

        points = await self.repository.list_tree_snapshot_points(
            db=db,
            include_archived=include_archived,
        )
        nodes = [self._to_snapshot_node(point) for point in points]
        await cache.set(
            cache_key,
            [node.model_dump(mode="json") for node in nodes],
            ttl_seconds=KNOWLEDGE_TREE_CACHE_TTL_SECONDS,
        )
        return nodes

    @staticmethod
    def _build_cache_key(*, include_archived: bool) -> str:
        """生成知识点树缓存 key。"""

        scope = "all" if include_archived else "active"
        return f"{KNOWLEDGE_TREE_CACHE_PREFIX}{scope}"

    @staticmethod
    def _to_snapshot_node(point: KnowledgePoint) -> KnowledgeTreeSnapshotNode:
        """把 ORM 节点转换为缓存快照节点。"""

        return KnowledgeTreeSnapshotNode(
            id=point.id,
            skill_id=point.skill_id,
            parent_id=point.parent_id,
            title=point.title,
            summary=point.summary,
            level=point.level,
            depth=point.depth,
            sort_order=point.sort_order,
            status=point.status,
            created_at=point.created_at,
            updated_at=point.updated_at,
        )
