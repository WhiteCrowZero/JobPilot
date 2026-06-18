from __future__ import annotations

from typing import cast

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from job_pilot.core.search import (
    SearchBackend,
    SortMap,
    apply_sort_by_key,
    clean_optional_text,
    fetch_offset_page,
)
from job_pilot.modules.knowledge.contracts import KnowledgePointSearchQuery
from job_pilot.modules.knowledge.enums import KnowledgePointStatus
from job_pilot.modules.knowledge.models import KnowledgePoint

KNOWLEDGE_POINT_DEFAULT_SORT = "directory"
KNOWLEDGE_POINT_SORTS: SortMap = {
    KNOWLEDGE_POINT_DEFAULT_SORT: lambda: cast(
        tuple[ColumnElement[object], ...],
        (
            KnowledgePoint.skill_id.asc(),
            KnowledgePoint.depth.asc(),
            KnowledgePoint.parent_id.asc().nulls_first(),
            KnowledgePoint.sort_order.asc(),
            KnowledgePoint.id.asc(),
        ),
    ),
}


class KnowledgeRepository:
    """知识点数据库操作。"""

    def __init__(self, search_backend: SearchBackend) -> None:
        self.search_backend = search_backend

    async def search_knowledge_points(
        self,
        *,
        db: AsyncSession,
        params: KnowledgePointSearchQuery,
    ) -> list[KnowledgePoint]:
        """按条件查询知识点列表，多取一条用于判断 has_next。"""

        stmt = self._build_knowledge_points_stmt(params)
        stmt = self._apply_default_order(stmt)
        return await fetch_offset_page(
            db,
            stmt,
            offset=params.offset,
            limit=params.limit,
        )

    async def get_knowledge_point(
        self,
        *,
        db: AsyncSession,
        knowledge_point_id: int,
    ) -> KnowledgePoint | None:
        """按主键读取知识点，用于查询入口参数校验。"""

        stmt = select(KnowledgePoint).where(KnowledgePoint.id == knowledge_point_id)
        return await db.scalar(stmt)

    async def list_tree_snapshot_points(
        self,
        *,
        db: AsyncSession,
        include_archived: bool,
    ) -> list[KnowledgePoint]:
        """读取完整知识点树快照，供缓存构建使用。"""

        conditions: list[ColumnElement[bool]] = []
        if not include_archived:
            conditions.append(KnowledgePoint.status == KnowledgePointStatus.ACTIVE)

        stmt = (
            select(KnowledgePoint)
            .where(*conditions)
            .order_by(
                KnowledgePoint.skill_id.asc(),
                KnowledgePoint.depth.asc(),
                KnowledgePoint.parent_id.asc().nulls_first(),
                KnowledgePoint.sort_order.asc(),
                KnowledgePoint.id.asc(),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _build_knowledge_points_stmt(
        self, params: KnowledgePointSearchQuery
    ) -> Select[tuple[KnowledgePoint]]:
        stmt = select(KnowledgePoint)

        conditions: list[ColumnElement[bool]] = []

        conditions.append(KnowledgePoint.status == KnowledgePointStatus.ACTIVE)
        if params.skill_id is not None:
            conditions.append(KnowledgePoint.skill_id == params.skill_id)
        if params.levels:
            conditions.append(KnowledgePoint.level.in_(params.levels))

        keyword = clean_optional_text(params.keyword)
        if keyword is not None:
            conditions.append(
                self.search_backend.contains_text_in_any_field(
                    (
                        KnowledgePoint.title,
                        KnowledgePoint.summary,
                    ),
                    keyword,
                )
            )

        if not conditions:
            return stmt
        return stmt.where(and_(*conditions))

    def _apply_default_order(
        self,
        stmt: Select[tuple[KnowledgePoint]],
    ) -> Select[tuple[KnowledgePoint]]:
        """按知识点目录顺序返回列表。"""

        return apply_sort_by_key(
            stmt,
            sort_key=KNOWLEDGE_POINT_DEFAULT_SORT,
            sort_map=KNOWLEDGE_POINT_SORTS,
            error_label="knowledge point",
        )
