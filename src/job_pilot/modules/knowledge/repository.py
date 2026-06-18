from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement, TextClause

from job_pilot.modules.knowledge.contracts import KnowledgeTreeQuery
from job_pilot.modules.knowledge.enums import KnowledgePointStatus
from job_pilot.modules.knowledge.models import KnowledgePoint


class KnowledgeRepository:
    """知识点树数据库操作。"""

    async def count_tree_roots(self, db: AsyncSession, params: KnowledgeTreeQuery) -> int:
        """统计当前查询起点节点数量。"""

        stmt = select(func.count(KnowledgePoint.id)).where(*self._build_root_conditions(params))
        result = await db.execute(stmt)
        return result.scalar_one()

    async def list_tree_points(
        self,
        db: AsyncSession,
        params: KnowledgeTreeQuery,
    ) -> list[KnowledgePoint]:
        """使用递归 CTE 读取起点节点及其全部后代节点。"""

        stmt = select(KnowledgePoint).from_statement(self._build_tree_stmt(params))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _build_root_conditions(self, params: KnowledgeTreeQuery) -> list[ColumnElement[bool]]:
        """构造递归 CTE 起点条件。"""

        conditions: list[ColumnElement[bool]] = []
        if params.skill_id is not None:
            conditions.append(KnowledgePoint.skill_id == params.skill_id)
        if params.parent_id is None:
            conditions.append(KnowledgePoint.parent_id.is_(None))
        else:
            conditions.append(KnowledgePoint.parent_id == params.parent_id)
        if not params.include_archived:
            conditions.append(KnowledgePoint.status == KnowledgePointStatus.ACTIVE)
        return conditions

    def _build_tree_stmt(self, params: KnowledgeTreeQuery) -> TextClause:
        """构造递归查询 SQL，SQL 只返回 ORM 映射需要的知识点列。"""

        return text(
            """
            WITH RECURSIVE knowledge_tree AS (
                SELECT root.*
                FROM knowledge_points root
                WHERE (:skill_id IS NULL OR root.skill_id = :skill_id)
                  AND (
                      (:parent_id IS NULL AND root.parent_id IS NULL)
                      OR (:parent_id IS NOT NULL AND root.parent_id = :parent_id)
                  )
                  AND (:include_archived OR root.status = :active_status)

                UNION ALL

                SELECT child.*
                FROM knowledge_points child
                JOIN knowledge_tree parent_tree ON child.parent_id = parent_tree.id
                WHERE (:include_archived OR child.status = :active_status)
            )
            SELECT
                id,
                created_at,
                updated_at,
                skill_id,
                parent_id,
                title,
                summary,
                level,
                depth,
                sort_order,
                status
            FROM knowledge_tree
            ORDER BY skill_id, depth, parent_id NULLS FIRST, sort_order, id
            """
        ).bindparams(
            bindparam("skill_id", params.skill_id, type_=Integer),
            bindparam("parent_id", params.parent_id, type_=BigInteger),
            bindparam("include_archived", params.include_archived, type_=Boolean),
            bindparam("active_status", KnowledgePointStatus.ACTIVE.value, type_=String),
        )
