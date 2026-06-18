from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.core.resources import AppResources
from job_pilot.modules.knowledge.contracts import KnowledgePointSearchQuery, KnowledgeTreeQuery
from job_pilot.modules.knowledge.enums import KnowledgePointLevel, KnowledgePointStatus
from job_pilot.modules.knowledge.exceptions import KnowledgeTreeScopeMismatchError
from job_pilot.modules.knowledge.models import KnowledgePoint
from job_pilot.modules.knowledge.service import KNOWLEDGE_TREE_CACHE_PREFIX
from tests.helpers.builders import seed_test_skill
from tests.helpers.cache import MemoryCacheStore
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
async def test_get_knowledge_tree_builds_subtree_from_root(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """按 root_id 查询时以该节点作为返回树根。"""

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
            KnowledgeTreeQuery(root_id=root.id, page=1, page_size=10)
        )

        assert result.total == 1
        assert result.items[0].skill_id == python.id
        assert [node.title for node in result.items[0].tree] == ["Python 基础"]
        assert [node.title for node in result.items[0].tree[0].children] == ["语法"]
        assert [node.title for node in result.items[0].tree[0].children[0].children] == ["函数"]
    finally:
        await truncate_knowledge_tables(db_session)


@pytest.mark.asyncio
async def test_get_knowledge_tree_hides_archived_points(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """用户侧知识点树固定隐藏归档节点。"""

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
            KnowledgeTreeQuery(skill_id=python.id, page=1, page_size=10)
        )

        assert result.items[0].tree[0].children == []
    finally:
        await truncate_knowledge_tables(db_session)


@pytest.mark.asyncio
async def test_get_knowledge_tree_rejects_mismatched_skill_and_root(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """同时传 skill_id/root_id 时，root_id 必须属于该技能。"""

    await truncate_knowledge_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        database = await seed_test_skill(db_session, "Database")
        root = await seed_knowledge_point(db_session, skill_id=database.id, title="索引")

        with pytest.raises(KnowledgeTreeScopeMismatchError):
            await pilot.learning.get_knowledge_tree(
                KnowledgeTreeQuery(skill_id=python.id, root_id=root.id, page=1, page_size=10)
            )
    finally:
        await truncate_knowledge_tables(db_session)


@pytest.mark.asyncio
async def test_get_knowledge_tree_reuses_cached_snapshot(
    pilot: JobPilot,
    pilot_resources: AppResources,
    db_session: AsyncSession,
) -> None:
    """知识点树使用完整树快照缓存，避免重复回源。"""

    await truncate_knowledge_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        root = await seed_knowledge_point(db_session, skill_id=python.id, title="Python 基础")

        first_result = await pilot.learning.get_knowledge_tree(
            KnowledgeTreeQuery(skill_id=python.id, page=1, page_size=10)
        )
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="语法",
            parent_id=root.id,
            depth=1,
        )
        second_result = await pilot.learning.get_knowledge_tree(
            KnowledgeTreeQuery(skill_id=python.id, page=1, page_size=10)
        )

        assert isinstance(pilot_resources.cache, MemoryCacheStore)
        assert f"{KNOWLEDGE_TREE_CACHE_PREFIX}active" in pilot_resources.cache.items
        assert [node.title for node in first_result.items[0].tree] == ["Python 基础"]
        assert second_result.items[0].tree[0].children == []
    finally:
        await truncate_knowledge_tables(db_session)


@pytest.mark.asyncio
async def test_search_knowledge_points_filters_by_keyword_level_and_skill(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """知识点搜索按技能、关键词和难度返回普通列表。"""

    await truncate_knowledge_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        database = await seed_test_skill(db_session, "Database")
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="Python 生成器",
            summary="yield 惰性迭代",
            level=KnowledgePointLevel.INTERMEDIATE,
        )
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="装饰器",
            level=KnowledgePointLevel.ADVANCED,
        )
        await seed_knowledge_point(
            db_session,
            skill_id=database.id,
            title="生成器模式",
            level=KnowledgePointLevel.INTERMEDIATE,
        )

        result = await pilot.learning.search_knowledge_points(
            KnowledgePointSearchQuery(
                skill_id=python.id,
                keyword="生成器",
                levels=[KnowledgePointLevel.INTERMEDIATE],
                page=1,
                page_size=10,
            )
        )

        assert result.has_next is False
        assert [item.title for item in result.items] == ["Python 生成器"]
        assert result.items[0].skill_id == python.id
        assert result.items[0].level is KnowledgePointLevel.INTERMEDIATE
    finally:
        await truncate_knowledge_tables(db_session)


@pytest.mark.asyncio
async def test_search_knowledge_points_hides_archived_points(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """用户侧知识点搜索固定隐藏归档节点。"""

    await truncate_knowledge_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="Python 生成器",
        )
        await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="生成器历史",
            status=KnowledgePointStatus.ARCHIVED,
        )

        result = await pilot.learning.search_knowledge_points(
            KnowledgePointSearchQuery(keyword="生成器", page=1, page_size=10)
        )

        assert [item.title for item in result.items] == ["Python 生成器"]
        assert all(item.skill_id == python.id for item in result.items)
    finally:
        await truncate_knowledge_tables(db_session)


async def seed_knowledge_point(
    session: AsyncSession,
    *,
    skill_id: int,
    title: str,
    summary: str | None = None,
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
        summary=summary,
        level=level,
        depth=depth,
        sort_order=sort_order,
        status=status,
    )
    session.add(point)
    await session.commit()
    await session.refresh(point)
    return point
