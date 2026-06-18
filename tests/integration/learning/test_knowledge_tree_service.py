from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.knowledge.contracts import KnowledgeTreeQuery
from job_pilot.modules.knowledge.enums import KnowledgePointLevel, KnowledgePointStatus
from job_pilot.modules.knowledge.models import KnowledgePoint
from tests.helpers.builders import seed_test_skill
from tests.helpers.database import truncate_knowledge_tables


@pytest.mark.asyncio
async def test_get_knowledge_tree_builds_active_tree_by_skill(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """知识点树按技能递归读取 active 节点并组装父子层级。"""

    await truncate_knowledge_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        root = await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="Python 基础",
            sort_order=1,
        )
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="语法",
            parent_id=root.id,
            depth=1,
            sort_order=1,
        )
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="解释器",
            parent_id=root.id,
            depth=1,
            sort_order=2,
            status=KnowledgePointStatus.ARCHIVED,
        )

        result = await pilot.learning.get_knowledge_tree(
            KnowledgeTreeQuery(skill_id=python.id, page=1, page_size=10)
        )

        assert result.total == 1
        assert result.has_next is False
        assert result.items[0].skill_id == python.id
        assert [node.title for node in result.items[0].tree] == ["Python 基础"]
        assert [node.title for node in result.items[0].tree[0].children] == ["语法"]
        assert result.items[0].tree[0].level is KnowledgePointLevel.BASIC
        assert result.items[0].tree[0].status is KnowledgePointStatus.ACTIVE
    finally:
        await truncate_knowledge_tables(db_session)


@pytest.mark.asyncio
async def test_get_knowledge_tree_builds_subtree_from_parent(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """按 parent_id 查询时直接子节点作为返回树根。"""

    await truncate_knowledge_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        root = await seed_knowledge_point(db_session, skill_id=python.id, title="Python 基础")
        syntax = await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="语法",
            parent_id=root.id,
            depth=1,
            sort_order=1,
        )
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="函数",
            parent_id=syntax.id,
            depth=2,
            sort_order=1,
        )

        result = await pilot.learning.get_knowledge_tree(
            KnowledgeTreeQuery(parent_id=root.id, page=1, page_size=10)
        )

        assert result.total == 1
        assert result.items[0].skill_id == python.id
        assert [node.title for node in result.items[0].tree] == ["语法"]
        assert [node.title for node in result.items[0].tree[0].children] == ["函数"]
    finally:
        await truncate_knowledge_tables(db_session)


@pytest.mark.asyncio
async def test_get_knowledge_tree_can_include_archived_points(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """include_archived 为 true 时递归树包含归档节点。"""

    await truncate_knowledge_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        root = await seed_knowledge_point(db_session, skill_id=python.id, title="Python 基础")
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="历史版本",
            parent_id=root.id,
            depth=1,
            status=KnowledgePointStatus.ARCHIVED,
        )

        result = await pilot.learning.get_knowledge_tree(
            KnowledgeTreeQuery(
                skill_id=python.id,
                include_archived=True,
                page=1,
                page_size=10,
            )
        )

        assert [node.title for node in result.items[0].tree[0].children] == ["历史版本"]
        assert result.items[0].tree[0].children[0].status is KnowledgePointStatus.ARCHIVED
    finally:
        await truncate_knowledge_tables(db_session)


async def seed_knowledge_point(
    session: AsyncSession,
    *,
    skill_id: int,
    title: str,
    parent_id: int | None = None,
    depth: int = 0,
    sort_order: int = 1,
    level: KnowledgePointLevel = KnowledgePointLevel.BASIC,
    status: KnowledgePointStatus = KnowledgePointStatus.ACTIVE,
) -> KnowledgePoint:
    """创建测试知识点并刷新服务端时间字段。"""

    point = KnowledgePoint(
        skill_id=skill_id,
        parent_id=parent_id,
        title=title,
        level=level,
        depth=depth,
        sort_order=sort_order,
        status=status,
    )
    session.add(point)
    await session.commit()
    await session.refresh(point)
    return point
