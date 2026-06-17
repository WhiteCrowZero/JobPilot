from __future__ import annotations

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.service import JobSourceConfig
from job_pilot.modules.job_posts.enums import JobPostStatus
from job_pilot.modules.job_posts.models import JobPost
from job_pilot.modules.job_posts.schemas import JobPostSearchParams
from job_pilot.modules.job_skills.repository import SkillDictionaryRepository
from job_pilot.modules.job_skills.schemas import SkillListParams
from job_pilot.modules.job_skills.skill_sync_contracts import RawSkillCandidate
from tests.helpers.database import truncate_job_tables


@pytest.mark.asyncio
async def test_list_standard_skills_under_jobs_domain(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """通过公开入口查询标准技能字典。"""

    await truncate_job_tables(db_session)
    await seed_test_skills(db_session)

    try:
        response = await pilot.skills.list_skills(
            SkillListParams(keyword="py", page=1, page_size=20)
        )

        assert response.total == 1
        assert [(item.id, item.name) for item in response.items] == [(1, "Python")]
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_with_multiple_filters(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位搜索支持关键词、地点、薪资和枚举筛选。"""

    await seed_job_posts(pilot=pilot, session=db_session)

    try:
        response = await pilot.job_posts.search(
            JobPostSearchParams(
                keyword="FastAPI",
                locations=["北京"],
                salary_min=15000,
                salary_max=35000,
                employment_types=["unknown"],  # type: ignore[list-item]
                page=1,
                page_size=10,
            )
        )

        assert len(response.items) == 1
        assert response.page == 1
        assert response.page_size == 10
        assert response.total is None
        assert response.has_next is False
        assert response.items[0].title == "后端开发工程师"
        assert response.items[0].locations == "北京 / 中国"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_supports_remote_and_status_filters(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位搜索支持远程和状态筛选。"""

    closed_job_id = await seed_job_posts(pilot=pilot, session=db_session)
    await db_session.execute(
        update(JobPost).where(JobPost.id == closed_job_id).values(status=JobPostStatus.CLOSED)
    )
    await db_session.commit()

    try:
        default_response = await pilot.job_posts.search(JobPostSearchParams(page=1, page_size=20))
        remote_response = await pilot.job_posts.search(
            JobPostSearchParams(
                workplace_types=["remote"],  # type: ignore[list-item]
                is_remote=True,
                page=1,
                page_size=20,
            )
        )
        closed_response = await pilot.job_posts.search(
            JobPostSearchParams(
                statuses=[JobPostStatus.CLOSED],
                include_closed=True,
                page=1,
                page_size=20,
            )
        )

        assert len(default_response.items) == 1
        assert len(remote_response.items) == 1
        assert remote_response.items[0].title == "Backend Engineer"
        assert remote_response.items[0].is_remote is True
        assert len(closed_response.items) == 1
        assert closed_response.items[0].status == JobPostStatus.CLOSED
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_supports_skill_filters(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位搜索支持技能标签交集筛选。"""

    await seed_job_posts(pilot=pilot, session=db_session)

    try:
        python_response = await pilot.job_posts.search(
            JobPostSearchParams(skill_ids=[1], page=1, page_size=20)
        )
        redis_response = await pilot.job_posts.search(
            JobPostSearchParams(skill_ids=[3], page=1, page_size=20)
        )
        impossible_response = await pilot.job_posts.search(
            JobPostSearchParams(skill_ids=[1, 3], page=1, page_size=20)
        )

        assert [item.title for item in python_response.items] == ["后端开发工程师"]
        assert [item.title for item in redis_response.items] == ["Backend Engineer"]
        assert impossible_response.items == []
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_uses_page_pagination(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位搜索使用 has_next 分页模型。"""

    await seed_job_posts(pilot=pilot, session=db_session)

    try:
        first_page = await pilot.job_posts.search(JobPostSearchParams(page=1, page_size=1))
        second_page = await pilot.job_posts.search(JobPostSearchParams(page=2, page_size=1))

        assert first_page.page == 1
        assert first_page.page_size == 1
        assert first_page.total is None
        assert first_page.has_next is True
        assert len(first_page.items) == 1
        assert second_page.page == 2
        assert second_page.page_size == 1
        assert second_page.total is None
        assert second_page.has_next is False
        assert len(second_page.items) == 1
        assert second_page.items[0].title == "后端开发工程师"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_read_job_post_detail_and_filter_options(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """岗位详情和筛选项候选值通过公开入口读取。"""

    closed_job_id = await seed_job_posts(pilot=pilot, session=db_session)
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

        assert detail.title == "Backend Engineer"
        assert detail.source_name == "Jaabz"
        assert detail.source_base_url == "https://jaabz.com/jobs"
        assert detail.source_url == "https://jobs.example.com/jb-001"
        assert detail.locations == "Remote"
        assert detail.is_remote is True
        assert detail.has_relocation_support is True
        assert [(skill.id, skill.name) for skill in detail.skills] == [
            (2, "FastAPI"),
            (3, "Redis"),
        ]

        assert "alibaba" not in options.source_platforms
        assert "jaabz" in options.source_platforms
        assert "北京 / 中国" not in options.locations
        assert "Remote" in options.locations
        assert (1, "Python") in [(skill.id, skill.name) for skill in options.skills]
        assert (2, "FastAPI") in [(skill.id, skill.name) for skill in options.skills]
    finally:
        await truncate_job_tables(db_session)


async def seed_job_posts(*, pilot: JobPilot, session: AsyncSession) -> int:
    """构造岗位查询集成测试数据。"""

    await truncate_job_tables(session)
    await seed_test_skills(session)

    alibaba_result = await pilot.ingestion.consume_raw_job(
        source_config=JobSourceConfig(
            platform="alibaba",
            name="阿里巴巴社招",
            base_url="https://talent.taotian.com/off-campus",
        ),
        message=RawJobCollectedMessage(
            message_id="job-query-test:alibaba",
            source_platform="alibaba",
            external_job_id="ali-query-001",
            source_url="https://jobs.example.com/ali-query-001",
            producer="alijob_crawler",
            raw_payload={
                "job_id": "ali-query-001",
                "job_url": "https://jobs.example.com/ali-query-001",
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
    assert alibaba_result.job_post_id is not None
    await pilot.skills.sync_job_skills(
        job_post_id=alibaba_result.job_post_id,
        candidates=[RawSkillCandidate("Python"), RawSkillCandidate("Fast API")],
    )

    jaabz_result = await pilot.ingestion.consume_raw_job(
        source_config=JobSourceConfig(
            platform="jaabz",
            name="Jaabz",
            base_url="https://jaabz.com/jobs",
        ),
        message=RawJobCollectedMessage(
            message_id="job-query-test:jaabz",
            source_platform="jaabz",
            external_job_id="jb-query-001",
            source_url="https://jobs.example.com/jb-001",
            producer="jaabz_crawler",
            raw_payload={
                "job_id": "jb-query-001",
                "job_url": "https://jobs.example.com/jb-001",
                "title": "Backend Engineer",
                "company_name": "Remote Tech",
                "company_url": "https://company.example.com",
                "area": "Remote",
                "details": "Build APIs with visa sponsorship and relocation support.",
                "experience": "5+ years",
                "job_type": "full-time",
                "flexibility": "remote",
                "salary": "100-150K/year",
                "release_time": "2026-06-02",
            },
        ),
    )
    assert jaabz_result.job_post_id is not None
    await pilot.skills.sync_job_skills(
        job_post_id=jaabz_result.job_post_id,
        candidates=[RawSkillCandidate("FastAPI"), RawSkillCandidate("Redis")],
    )
    return alibaba_result.job_post_id


async def seed_test_skills(session: AsyncSession) -> None:
    """构造技能字典数据。"""

    repository = SkillDictionaryRepository()
    seed_items = [
        ("Python", ["python", "py"]),
        ("FastAPI", ["fastapi"]),
        ("Redis", ["redis"]),
    ]
    for skill_name, aliases in seed_items:
        skill, _ = await repository.upsert_skill(db=session, name=skill_name)
        for alias in aliases:
            await repository.upsert_alias(db=session, skill_id=skill.id, alias=alias)
    await session.commit()
