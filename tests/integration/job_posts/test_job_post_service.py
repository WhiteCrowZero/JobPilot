from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.core.search import SqlLikeSearchBackend
from job_pilot.modules.ingestion.service import JobSourceConfig
from job_pilot.modules.job_posts.contracts import JobPostSearchQuery, JobPostSort
from job_pilot.modules.job_posts.enums import EducationLevel, JobPostStatus
from job_pilot.modules.job_posts.models import JobPost
from job_pilot.modules.job_skills.contracts import RawSkillCandidate
from job_pilot.modules.job_skills.repository import SkillDictionaryRepository
from job_pilot.modules.job_skills.schemas import SkillListParams
from tests.helpers.database import truncate_job_tables
from tests.helpers.messages import build_test_raw_job_message


@pytest.mark.asyncio
async def test_list_standard_skills_under_jobs_domain(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """通过公开入口查询标准技能字典。"""

    await truncate_job_tables(db_session)
    await _seed_test_skills(db_session)
    try:
        response = await pilot.skills.list_skills(
            SkillListParams(keyword="py", page=1, page_size=20)
        )

        assert response.total == 1
        assert [(item.id, item.name) for item in response.items] == [(1, "Python")]
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_with_confirmed_filters(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位搜索支持关键词、地点、来源和学历筛选。"""

    await _seed_job_posts(pilot=pilot, session=db_session)
    try:
        response = await pilot.job_posts.search(
            JobPostSearchQuery(
                keyword="FastAPI",
                locations=["北京"],
                source_platforms=["taotian"],
                education_levels=[EducationLevel.BACHELOR],
                page=1,
                page_size=10,
            )
        )

        assert len(response.items) == 1
        assert response.total is None
        assert response.has_next is False
        assert response.items[0].title == "后端开发工程师"
        assert response.items[0].locations == "北京"
        assert response.items[0].experience_text == "3-5年"
        assert response.items[0].salary_text == "20-30K"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_defaults_to_open_and_accepts_status_filter(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位列表默认仅展示 open，显式 statuses 可查询关闭岗位。"""

    closed_job_id = await _seed_job_posts(pilot=pilot, session=db_session)
    await db_session.execute(
        update(JobPost).where(JobPost.id == closed_job_id).values(status=JobPostStatus.CLOSED)
    )
    await db_session.commit()
    try:
        default_response = await pilot.job_posts.search(JobPostSearchQuery(page=1, page_size=20))
        closed_response = await pilot.job_posts.search(
            JobPostSearchQuery(statuses=[JobPostStatus.CLOSED], page=1, page_size=20)
        )

        assert [item.title for item in default_response.items] == ["Backend Engineer"]
        assert [item.title for item in closed_response.items] == ["后端开发工程师"]
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_supports_all_current_sort_keys(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位搜索只支持当前模型仍有数据依据的排序白名单。"""

    await _seed_job_posts(pilot=pilot, session=db_session)
    try:
        sort_expectations = {
            "published_at_desc": ["Backend Engineer", "后端开发工程师"],
            "published_at_asc": ["后端开发工程师", "Backend Engineer"],
            "created_at_desc": ["Backend Engineer", "后端开发工程师"],
            "created_at_asc": ["后端开发工程师", "Backend Engineer"],
        }
        for sort_key, expected_titles in sort_expectations.items():
            response = await pilot.job_posts.search(
                JobPostSearchQuery(
                    sort=cast(JobPostSort, sort_key),
                    page=1,
                    page_size=20,
                )
            )
            assert [item.title for item in response.items] == expected_titles
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_supports_skill_filters(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """既有岗位技能关系仍可用于技能交集筛选。"""

    await _seed_job_posts(pilot=pilot, session=db_session)
    try:
        python_response = await pilot.job_posts.search(
            JobPostSearchQuery(skill_ids=[1], page=1, page_size=20)
        )
        impossible_response = await pilot.job_posts.search(
            JobPostSearchQuery(skill_ids=[1, 3], page=1, page_size=20)
        )

        assert [item.title for item in python_response.items] == ["后端开发工程师"]
        assert impossible_response.items == []
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_uses_has_next_pagination(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位搜索通过多取一条计算 has_next。"""

    await _seed_job_posts(pilot=pilot, session=db_session)
    try:
        first_page = await pilot.job_posts.search(JobPostSearchQuery(page=1, page_size=1))
        second_page = await pilot.job_posts.search(JobPostSearchQuery(page=2, page_size=1))

        assert first_page.total is None
        assert first_page.has_next is True
        assert second_page.has_next is False
        assert second_page.items[0].title == "后端开发工程师"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_read_job_post_detail_and_filter_options(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位详情直接读取主表文本，筛选项只暴露现有结构。"""

    closed_job_id = await _seed_job_posts(pilot=pilot, session=db_session)
    await db_session.execute(
        update(JobPost).where(JobPost.id == closed_job_id).values(status=JobPostStatus.CLOSED)
    )
    await db_session.commit()
    try:
        job_post = await db_session.scalar(
            select(JobPost).where(JobPost.title == "Backend Engineer")
        )
        assert job_post is not None

        detail = await pilot.job_posts.get_detail(job_post_id=job_post.id)
        options = await pilot.job_posts.get_filter_options()

        assert detail.source_name == "腾讯招聘"
        assert detail.source_url == "https://jobs.example.com/tx-001"
        assert detail.description == "Build APIs.\n\nBachelor degree required."
        assert detail.experience_text == "5年以上"
        assert [(skill.id, skill.name) for skill in detail.skills] == [
            (2, "FastAPI"),
            (3, "Redis"),
        ]
        assert options.source_platforms == ["tencent"]
        assert options.locations == ["深圳"]
        assert EducationLevel.BACHELOR in options.education_levels
    finally:
        await truncate_job_tables(db_session)


async def _seed_job_posts(*, pilot: JobPilot, session: AsyncSession) -> int:
    """构造岗位查询集成测试数据。"""

    await truncate_job_tables(session)
    await _seed_test_skills(session)

    taotian_result = await pilot.ingestion.consume_raw_job(
        source_config=JobSourceConfig(
            platform="taotian",
            name="淘天招聘",
            base_url="https://talent.taotian.com",
        ),
        message=build_test_raw_job_message(
            message_id="job-query:taotian",
            source_platform="taotian",
            external_job_id="ali-query-001",
            source_url="https://jobs.example.com/ali-001",
            producer="taotian_crawler",
            raw_payload={
                "title": "后端开发工程师",
                "area": "北京",
                "description": "负责 FastAPI 后端服务建设。",
                "requirement": "本科，3-5年经验。",
                "experience": "3-5年",
                "degree": "本科",
                "salary": "20-30K",
                "publish_time": "2026-06-01",
            },
        ),
    )
    assert taotian_result.job_post_id is not None
    await pilot.skills.sync_job_skills(
        job_post_id=taotian_result.job_post_id,
        candidates=[RawSkillCandidate("Python"), RawSkillCandidate("Fast API")],
    )

    tencent_result = await pilot.ingestion.consume_raw_job(
        source_config=JobSourceConfig(
            platform="tencent",
            name="腾讯招聘",
            base_url="https://careers.tencent.com",
        ),
        message=build_test_raw_job_message(
            message_id="job-query:tencent",
            source_platform="tencent",
            external_job_id="tx-query-001",
            source_url="https://jobs.example.com/tx-001",
            producer="tencent_crawler",
            raw_payload={
                "job_name": "Backend Engineer",
                "city_name": "深圳",
                "job_desc": "Build APIs.",
                "requirement": "Bachelor degree required.",
                "experience": "5年以上",
                "degree": "本科",
                "publish_time": "2026-06-02",
            },
        ),
    )
    assert tencent_result.job_post_id is not None
    await pilot.skills.sync_job_skills(
        job_post_id=tencent_result.job_post_id,
        candidates=[RawSkillCandidate("FastAPI"), RawSkillCandidate("Redis")],
    )
    return taotian_result.job_post_id


async def _seed_test_skills(session: AsyncSession) -> None:
    """构造技能字典数据。"""

    repository = SkillDictionaryRepository(SqlLikeSearchBackend())
    seed_items = [
        ("Python", ["python", "py"]),
        ("FastAPI", ["fastapi", "fast api"]),
        ("Redis", ["redis"]),
    ]
    for skill_name, aliases in seed_items:
        skill, _ = await repository.upsert_skill(db=session, name=skill_name)
        for alias in aliases:
            await repository.upsert_alias(db=session, skill_id=skill.id, alias=alias)
    await session.commit()
