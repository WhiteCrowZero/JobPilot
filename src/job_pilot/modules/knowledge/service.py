from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.cache import CacheStore
from job_pilot.core.pagination import trim_page_items
from job_pilot.modules.knowledge.contracts import KnowledgeTreeQuery
from job_pilot.modules.knowledge.models import KnowledgePoint
from job_pilot.modules.knowledge.repository import KnowledgeRepository
from job_pilot.modules.knowledge.schemas import (
    KnowledgeTreeListResponse,
    KnowledgeTreeNode,
    KnowledgeTreeResponse,
)


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
        _ = cache
        flat_points = await self.repository.list_tree_points(db=db, params=params)
        tree_groups = self._build_tree_groups(flat_points)
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


def build_knowledge_service() -> KnowledgeService:
    """组装知识点树 service 的默认依赖。"""

    return KnowledgeService(
        repository=KnowledgeRepository(),
    )
