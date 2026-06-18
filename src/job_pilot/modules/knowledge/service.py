from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.cache import CacheStore
from job_pilot.core.pagination import trim_page_items
from job_pilot.core.search import SearchBackend
from job_pilot.modules.knowledge.contracts import KnowledgePointSearchQuery, KnowledgeTreeQuery
from job_pilot.modules.knowledge.enums import KnowledgePointStatus
from job_pilot.modules.knowledge.exceptions import (
    KnowledgePointNotFoundError,
    KnowledgeTreeScopeMismatchError,
)
from job_pilot.modules.knowledge.knowledge_tree.tree_builder import KnowledgeTreeBuilder
from job_pilot.modules.knowledge.knowledge_tree.tree_cache import KnowledgeTreeSnapshotProvider
from job_pilot.modules.knowledge.models import KnowledgePoint
from job_pilot.modules.knowledge.repository import KnowledgeRepository
from job_pilot.modules.knowledge.schemas import (
    KnowledgePointListItem,
    KnowledgePointListResponse,
    KnowledgeTreeListResponse,
)


class KnowledgeService:
    """知识点树 service，负责树结构组装和响应转换。"""

    def __init__(
        self,
        repository: KnowledgeRepository,
        tree_snapshot_provider: KnowledgeTreeSnapshotProvider,
        tree_builder: KnowledgeTreeBuilder,
    ) -> None:
        self.repository = repository
        self.tree_snapshot_provider = tree_snapshot_provider
        self.tree_builder = tree_builder

    async def get_knowledge_trees(
        self,
        db: AsyncSession,
        *,
        params: KnowledgeTreeQuery,
        cache: CacheStore,
    ) -> KnowledgeTreeListResponse:
        await self._validate_tree_scope(db=db, params=params)

        nodes = await self.tree_snapshot_provider.get_nodes(
            db,
            cache=cache,
            include_archived=False,
        )
        tree_groups = self.tree_builder.build_tree_groups(nodes=nodes, params=params)
        page_slice = tree_groups[params.offset : params.offset + params.page_size + 1]
        page_items, has_next = trim_page_items(
            page_slice,
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


def build_knowledge_service(search_backend: SearchBackend) -> KnowledgeService:
    """组装知识点树 service 的默认依赖。"""

    repository = KnowledgeRepository(search_backend)
    return KnowledgeService(
        repository=repository,
        tree_snapshot_provider=KnowledgeTreeSnapshotProvider(repository),
        tree_builder=KnowledgeTreeBuilder(),
    )
