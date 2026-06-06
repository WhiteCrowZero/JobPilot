from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.service import JobSourceConfig, RawJobIngestionService
from job_pilot.modules.job_posts.enums import JobPostStatus
from job_pilot.modules.job_posts.models import JobPost
from tests.api.endpoints import (
    JOBS_ENDPOINT,
    JOBS_FILTER_OPTIONS_ENDPOINT,
    job_detail_endpoint,
)


@pytest.mark.asyncio
async def test_search_job_posts_with_multiple_filters(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_job_posts(db_session)

    try:
        response = await api_client.get(
            JOBS_ENDPOINT,
            params=[
                ("keyword", "FastAPI"),
                ("locations", "北京"),
                ("salary_min", "15000"),
                ("salary_max", "35000"),
                ("employment_types", "unknown"),
                ("page_size", "10"),
            ],
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["title"] == "后端开发工程师"
        assert payload["items"][0]["locations"] == "北京 / 中国"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_supports_remote_and_status_filters(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    closed_job_id = await seed_job_posts(db_session)
    await db_session.execute(
        update(JobPost).where(JobPost.id == closed_job_id).values(status=JobPostStatus.CLOSED)
    )
    await db_session.commit()

    try:
        default_response = await api_client.get(JOBS_ENDPOINT)
        remote_response = await api_client.get(
            JOBS_ENDPOINT,
            params=[
                ("workplace_types", "remote"),
                ("is_remote", "true"),
            ],
        )
        closed_response = await api_client.get(
            JOBS_ENDPOINT,
            params=[
                ("statuses", "closed"),
                ("include_closed", "true"),
            ],
        )

        assert default_response.status_code == 200
        assert default_response.json()["total"] == 1
        assert remote_response.status_code == 200
        assert remote_response.json()["total"] == 1
        assert remote_response.json()["items"][0]["title"] == "Backend Engineer"
        assert remote_response.json()["items"][0]["is_remote"] is True
        assert closed_response.status_code == 200
        assert closed_response.json()["total"] == 1
        assert closed_response.json()["items"][0]["status"] == "closed"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_read_job_post_detail_and_filter_options(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_job_posts(db_session)

    try:
        job_post = await db_session.scalar(
            select(JobPost).where(JobPost.title == "Backend Engineer")
        )
        assert job_post is not None

        detail_response = await api_client.get(job_detail_endpoint(job_post.id))
        filter_options_response = await api_client.get(JOBS_FILTER_OPTIONS_ENDPOINT)

        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["title"] == "Backend Engineer"
        assert detail_payload["source_name"] == "Jaabz"
        assert detail_payload["source_base_url"] == "https://jaabz.com/jobs"
        assert detail_payload["source_url"] == "https://jobs.example.com/jb-001"
        assert detail_payload["locations"] == "Remote"
        assert detail_payload["is_remote"] is True
        assert detail_payload["has_relocation_support"] is True

        assert filter_options_response.status_code == 200
        options_payload = filter_options_response.json()
        assert "alibaba" in options_payload["source_platforms"]
        assert "jaabz" in options_payload["source_platforms"]
        assert "北京 / 中国" in options_payload["locations"]
        assert "CNY" in options_payload["salary_currencies"]
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_read_missing_job_post_returns_404(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(job_detail_endpoint(999_999))

    assert response.status_code == 404
    assert response.json()["code"] == "JOB_POST_NOT_FOUND"


async def seed_job_posts(session: AsyncSession) -> int:
    await truncate_job_tables(session)
    alibaba_service = RawJobIngestionService(
        source_config=JobSourceConfig(
            platform="alibaba",
            name="阿里巴巴社招",
            base_url="https://talent.taotian.com/off-campus",
        )
    )
    jaabz_service = RawJobIngestionService(
        source_config=JobSourceConfig(
            platform="jaabz",
            name="Jaabz",
            base_url="https://jaabz.com/jobs",
        )
    )

    alibaba_result = await alibaba_service.consume_raw_job_message(
        session=session,
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
    await jaabz_service.consume_raw_job_message(
        session=session,
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
    await session.commit()
    return alibaba_result.job_post_id


async def truncate_job_tables(session: AsyncSession) -> None:
    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                job_post_details,
                job_posts,
                raw_job_records,
                job_sources
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()
