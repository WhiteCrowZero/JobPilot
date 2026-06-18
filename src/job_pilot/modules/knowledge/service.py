from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.cache import CacheStore
from job_pilot.core.pagination import trim_page_items
from job_pilot.core.search.backend import SearchBackend
from job_pilot.modules.knowledge.contracts import KnowledgePointSearchQuery, KnowledgeTreeQuery
from job_pilot.modules.knowledge.enums import KnowledgePointLevel, KnowledgePointStatus
from job_pilot.modules.knowledge.exceptions import (
    KnowledgePointNotFoundError,
    KnowledgeTreeScopeMismatchError,
)
from job_pilot.modules.knowledge.models import KnowledgePoint
from job_pilot.modules.knowledge.repository import KnowledgeRepository
from job_pilot.modules.knowledge.schemas import (
    KnowledgePointListItem,
    KnowledgePointListResponse,
    KnowledgeTreeListResponse,
    KnowledgeTreeNode,
    KnowledgeTreeResponse,
)

KNOWLEDGE_TREE_CACHE_PREFIX = "knowledge:tree:v1:"
KNOWLEDGE_TREE_CACHE_TTL_SECONDS = 60 * 60 * 6

logger = logging.getLogger(__name__)


class KnowledgeTreeSnapshotNode(BaseModel):
    """缓存中的知识点节点快照。"""

    id: int
    skill_id: int
    parent_id: int | None = None
    title: str
    summary: str | None = None
    level: KnowledgePointLevel
    depth: int
    sort_order: int
    status: KnowledgePointStatus
    created_at: datetime
    updated_at: datetime


class KnowledgeTreeSnapshot(BaseModel):
    """缓存中的知识点树索引，支持按 skill/root 快速组装树。"""

    nodes_by_id: dict[int, KnowledgeTreeSnapshotNode] = Field(default_factory=dict)
    root_ids_by_skill_id: dict[int, list[int]] = Field(default_factory=dict)
    child_ids_by_parent_id: dict[int, list[int]] = Field(default_factory=dict)
    skill_ids: list[int] = Field(default_factory=list)


class KnowledgeService:
    """知识点树 service，负责树结构组装和响应转换。"""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    async def get_knowledge_trees(
        self,
        db: AsyncSession,
        *,
        params: KnowledgeTreeQuery,
        cache: CacheStore,
    ) -> KnowledgeTreeListResponse:
        await self._validate_tree_scope(db=db, params=params)

        snapshot = await self._get_tree_snapshot(
            db=db,
            cache=cache,
            include_archived=False,
        )
        tree_groups = self._build_tree_groups_from_snapshot(snapshot=snapshot, params=params)
        page_items, has_next = trim_page_items(
            tree_groups,
            page_size=params.page_size,
        )
        return KnowledgeTreeListResponse(
            items=page_items,
            page=params.page,
            page_size=params.page_size,
            total=len(tree_groups),
            has_next=has_next,
        )

    async def search_knowledge_points(
        self,
        db: AsyncSession,
        *,
        params: KnowledgePointSearchQuery,
    ) -> KnowledgePointListResponse:
        knowledge_points = await self.repository.search_knowledge_points(db=db, params=params)
        page_items, has_next = trim_page_items(
            knowledge_points,
            page_size=params.page_size,
        )
        return KnowledgePointListResponse(
            items=[self._to_list_item(knowledge_point) for knowledge_point in page_items],
            page=params.page,
            page_size=params.page_size,
            total=None,
            has_next=has_next,
        )

    async def _validate_tree_scope(
        self,
        *,
        db: AsyncSession,
        params: KnowledgeTreeQuery,
    ) -> None:
        """校验 root_id 存在，且与 skill_id 指向同一棵树。"""

        if params.root_id is None:
            return

        root = await self.repository.get_knowledge_point(
            db=db,
            knowledge_point_id=params.root_id,
        )
        if root is None:
            raise KnowledgePointNotFoundError()
        if root.status is not KnowledgePointStatus.ACTIVE:
            raise KnowledgePointNotFoundError()
        if params.skill_id is not None and root.skill_id != params.skill_id:
            raise KnowledgeTreeScopeMismatchError(
                "root_id does not belong to the requested skill_id"
            )

    async def _get_tree_snapshot(
        self,
        *,
        db: AsyncSession,
        cache: CacheStore,
        include_archived: bool,
    ) -> KnowledgeTreeSnapshot:
        """读取树快照缓存，缓存损坏时回源数据库并重建。"""

        cache_key = self._build_tree_cache_key(include_archived=include_archived)
        cached_value = await cache.get(cache_key)
        if isinstance(cached_value, dict):
            try:
                return KnowledgeTreeSnapshot.model_validate(cached_value)
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
        snapshot = self._build_tree_snapshot(points)
        await cache.set(
            cache_key,
            snapshot.model_dump(mode="json"),
            ttl_seconds=KNOWLEDGE_TREE_CACHE_TTL_SECONDS,
        )
        return snapshot

    def _build_tree_snapshot(self, points: list[KnowledgePoint]) -> KnowledgeTreeSnapshot:
        """把数据库节点转成规范化树索引，避免按查询条件重复缓存树。"""

        nodes_by_id: dict[int, KnowledgeTreeSnapshotNode] = {}
        root_ids_by_skill_id: dict[int, list[int]] = {}
        child_ids_by_parent_id: dict[int, list[int]] = {}
        skill_ids: list[int] = []
        seen_skill_ids: set[int] = set()

        for point in points:
            nodes_by_id[point.id] = self._to_snapshot_node(point)
            if point.skill_id not in seen_skill_ids:
                skill_ids.append(point.skill_id)
                seen_skill_ids.add(point.skill_id)
            if point.parent_id is None:
                root_ids_by_skill_id.setdefault(point.skill_id, []).append(point.id)
                continue
            child_ids_by_parent_id.setdefault(point.parent_id, []).append(point.id)

        return KnowledgeTreeSnapshot(
            nodes_by_id=nodes_by_id,
            root_ids_by_skill_id=root_ids_by_skill_id,
            child_ids_by_parent_id=child_ids_by_parent_id,
            skill_ids=skill_ids,
        )

    def _build_tree_groups_from_snapshot(
        self,
        *,
        snapshot: KnowledgeTreeSnapshot,
        params: KnowledgeTreeQuery,
    ) -> list[KnowledgeTreeResponse]:
        """按查询入口从树快照组装响应树。"""

        if params.root_id is not None:
            root = snapshot.nodes_by_id.get(params.root_id)
            if root is None:
                return []
            return [
                KnowledgeTreeResponse(
                    skill_id=root.skill_id,
                    tree=[self._build_snapshot_tree_node(snapshot, root.id, seen=set())],
                )
            ]

        if params.skill_id is not None:
            root_ids = snapshot.root_ids_by_skill_id.get(params.skill_id, [])
            if not root_ids:
                return []
            return [
                KnowledgeTreeResponse(
                    skill_id=params.skill_id,
                    tree=[
                        self._build_snapshot_tree_node(snapshot, root_id, seen=set())
                        for root_id in root_ids
                    ],
                )
            ]

        tree_groups: list[KnowledgeTreeResponse] = []
        for skill_id in snapshot.skill_ids:
            root_ids = snapshot.root_ids_by_skill_id.get(skill_id, [])
            if not root_ids:
                continue
            tree_groups.append(
                KnowledgeTreeResponse(
                    skill_id=skill_id,
                    tree=[
                        self._build_snapshot_tree_node(snapshot, root_id, seen=set())
                        for root_id in root_ids
                    ],
                )
            )
        return tree_groups

    def _build_snapshot_tree_node(
        self,
        snapshot: KnowledgeTreeSnapshot,
        node_id: int,
        *,
        seen: set[int],
    ) -> KnowledgeTreeNode:
        """从快照递归组装响应节点，避免异常数据导致无限递归。"""

        node = snapshot.nodes_by_id[node_id]
        next_seen = seen | {node_id}
        children = [
            self._build_snapshot_tree_node(snapshot, child_id, seen=next_seen)
            for child_id in snapshot.child_ids_by_parent_id.get(node_id, [])
            if child_id not in next_seen and child_id in snapshot.nodes_by_id
        ]
        return KnowledgeTreeNode(
            id=node.id,
            title=node.title,
            summary=node.summary,
            level=node.level,
            depth=node.depth,
            sort_order=node.sort_order,
            status=node.status,
            created_at=node.created_at,
            updated_at=node.updated_at,
            children=children,
        )

    def _to_snapshot_node(self, point: KnowledgePoint) -> KnowledgeTreeSnapshotNode:
        """把 ORM 节点转换为可 JSON 序列化的缓存节点。"""

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

    def _build_tree_groups(self, points: list[KnowledgePoint]) -> list[KnowledgeTreeResponse]:
        """把递归 SQL 返回的扁平节点组装为按 skill_id 分组的树。"""

        node_by_id = {point.id: self._to_tree_node(point) for point in points}
        root_nodes_by_skill_id: dict[int, list[KnowledgeTreeNode]] = {}

        for point in points:
            node = node_by_id[point.id]
            parent_node = node_by_id.get(point.parent_id) if point.parent_id is not None else None
            if parent_node is None:
                root_nodes_by_skill_id.setdefault(point.skill_id, []).append(node)
                continue
            parent_node.children.append(node)

        return [
            KnowledgeTreeResponse(skill_id=skill_id, tree=tree)
            for skill_id, tree in root_nodes_by_skill_id.items()
        ]

    def _to_tree_node(self, point: KnowledgePoint) -> KnowledgeTreeNode:
        """把 ORM 知识点转换为响应节点，避免直接暴露 ORM relationship。"""

        return KnowledgeTreeNode(
            id=point.id,
            title=point.title,
            summary=point.summary,
            level=point.level,
            depth=point.depth,
            sort_order=point.sort_order,
            status=point.status,
            created_at=point.created_at,
            updated_at=point.updated_at,
        )

    @staticmethod
    def _to_list_item(knowledge_point: KnowledgePoint) -> KnowledgePointListItem:
        return KnowledgePointListItem(
            id=knowledge_point.id,
            skill_id=knowledge_point.skill_id,
            title=knowledge_point.title,
            summary=knowledge_point.summary,
            level=knowledge_point.level,
            updated_at=knowledge_point.updated_at,
            created_at=knowledge_point.created_at,
        )

    @staticmethod
    def _build_tree_cache_key(*, include_archived: bool) -> str:
        scope = "all" if include_archived else "active"
        return f"{KNOWLEDGE_TREE_CACHE_PREFIX}{scope}"


def build_knowledge_service(search_backend: SearchBackend) -> KnowledgeService:
    """组装知识点树 service 的默认依赖。"""

    return KnowledgeService(
        repository=KnowledgeRepository(search_backend),
    )
