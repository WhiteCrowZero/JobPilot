from __future__ import annotations

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.ingestion.adapters import JobDraft
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.enums import RawJobRecordStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.normalization import normalize_job_draft, normalize_salary
from job_pilot.modules.ingestion.repository import RawRecordIngestionAction
from job_pilot.modules.ingestion.service import JobSourceConfig, RawJobIngestionService
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    ExperienceLevel,
    WorkplaceType,
)
from job_pilot.modules.job_posts.models import (
    JobPost,
    JobPostDetail,
    JobSource,
)


def test_normalize_job_draft_splits_core_job_fields() -> None:
    draft = JobDraft(
        source_platform="alibaba",
        external_job_id="ali-001",
        source_url="https://jobs.example.com/ali-001",
        title="  后端开发工程师  ",
        company_name="阿里巴巴",
        company_url=None,
        raw_location_text="北京/上海/远程",
        raw_country_name="中国",
        raw_city_name=None,
        raw_description="负责 FastAPI 服务建设，提供签证支持和 relocation support。",
        raw_experience="3-5年",
        raw_education="本科",
        raw_employment_type="全职",
        raw_flexibility="混合办公",
        raw_salary="15-30K",
        raw_skills=None,
        published_at_raw="2026-06-01",
    )

    normalized = normalize_job_draft(draft)

    assert normalized.title == "后端开发工程师"
    assert normalized.salary_text == "15-30K"
    assert normalized.salary_min == 15000
    assert normalized.salary_max == 30000
    assert normalized.experience_level == ExperienceLevel.MID
    assert normalized.experience_min_years == 3
    assert normalized.experience_max_years == 5
    assert normalized.education_level == EducationLevel.BACHELOR
    assert normalized.workplace_type == WorkplaceType.REMOTE
    assert normalized.locations == "北京 / 上海 / 远程 / 中国"
    assert normalized.is_remote is True
    assert normalized.has_visa_sponsorship is True
    assert normalized.has_relocation_support is True


def test_normalize_salary_supports_common_text() -> None:
    monthly_salary = normalize_salary("20-30K·14薪")
    yearly_salary = normalize_salary("USD 80k-120k/year")
    daily_salary = normalize_salary("150-200元/天")
    salary_with_context = normalize_salary("岗位描述：薪资 1.5-2万/月，经验不限")
    negotiable_salary = normalize_salary("Salary: negotiable")
    experience_text = normalize_salary("岗位要求：3-5年经验，负责从0到1建设后端系统")
    payroll_experience_text = normalize_salary(
        "Minimum of 2-4 years of payroll processing experience.",
    )

    assert monthly_salary.salary_text == "20-30K·14薪"
    assert monthly_salary.salary_min == 20000
    assert monthly_salary.salary_max == 30000
    assert monthly_salary.salary_currency == "CNY"
    assert yearly_salary.salary_min == 80000
    assert yearly_salary.salary_max == 120000
    assert yearly_salary.salary_currency == "USD"
    assert daily_salary.salary_min == 150
    assert daily_salary.salary_max == 200
    assert salary_with_context.salary_text == "1.5-2万/月"
    assert salary_with_context.salary_min == 15000
    assert salary_with_context.salary_max == 20000
    assert negotiable_salary.salary_text == "Salary: negotiable"
    assert negotiable_salary.salary_min is None
    assert negotiable_salary.salary_max is None
    assert experience_text.salary_text is None
    assert payroll_experience_text.salary_text is None


def test_normalize_job_draft_does_not_extract_salary_from_description() -> None:
    draft = JobDraft(
        source_platform="jaabz",
        external_job_id="jb-001",
        source_url="https://jobs.example.com/jb-001",
        title="Backend Engineer",
        company_name="Remote Tech",
        company_url=None,
        raw_location_text="Remote",
        raw_country_name=None,
        raw_city_name=None,
        raw_description="岗位描述：薪资 1.5-2万/月，要求 3-5 年经验。",
        raw_experience="3-5 years",
        raw_education=None,
        raw_employment_type="full-time",
        raw_flexibility="remote",
        raw_salary=None,
        raw_skills=None,
        published_at_raw="2026-06-01",
    )

    normalized = normalize_job_draft(draft)

    assert normalized.salary_text is None
    assert normalized.salary_min is None
    assert normalized.salary_max is None


@pytest.mark.asyncio
async def test_consume_raw_job_message_normalizes_job_tables(db_session: AsyncSession) -> None:
    await truncate_job_tables(db_session)

    try:
        service = RawJobIngestionService(
            source_config=JobSourceConfig(
                platform="alibaba",
                name="阿里巴巴社招",
                base_url="https://talent.taotian.com/off-campus",
            )
        )
        message = RawJobCollectedMessage(
            message_id="alibaba:sample-001",
            source_platform="alibaba",
            external_job_id="ali-001",
            source_url="https://jobs.example.com/ali-001",
            producer="alijob_crawler",
            raw_payload={
                "job_id": "ali-001",
                "job_url": "https://jobs.example.com/ali-001",
                "title": "后端开发工程师",
                "area": "北京/上海",
                "description": "负责 FastAPI 后端服务建设。",
                "requirement": "本科，3-5年经验。",
                "experience": "3-5年",
                "degree": "本科",
                "salary": "20-30K",
                "publish_time": "2026-06-01",
            },
        )

        first_result = await service.consume_raw_job_message(
            session=db_session,
            message=message,
        )
        await db_session.commit()

        assert first_result.created_job_post is True

        job_post = (await db_session.execute(select(JobPost))).scalar_one()
        detail = (await db_session.execute(select(JobPostDetail))).scalar_one()
        raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()
        source = (await db_session.execute(select(JobSource))).scalar_one()

        assert source.platform == "alibaba"
        assert source.name == "阿里巴巴社招"
        assert source.base_url == "https://talent.taotian.com/off-campus"
        assert raw_record.status == RawJobRecordStatus.NORMALIZED
        assert raw_record.external_job_id == "ali-001"
        assert job_post.title == "后端开发工程师"
        assert job_post.locations == "北京 / 上海 / 中国"
        assert job_post.is_remote is False
        assert job_post.salary_text == "20-30K"
        assert job_post.salary_min == 20000
        assert job_post.salary_max == 30000
        assert job_post.experience_level == ExperienceLevel.MID
        assert job_post.education_level == EducationLevel.BACHELOR
        assert detail.description == "负责 FastAPI 后端服务建设。\n\n本科，3-5年经验。"

        updated_message = message.model_copy(
            update={
                "message_id": "alibaba:sample-002",
                "raw_payload": {
                    **message.raw_payload,
                    "salary": "30-40K",
                }
            }
        )
        second_result = await service.consume_raw_job_message(
            session=db_session,
            message=updated_message,
        )
        await db_session.commit()

        job_post_count = await db_session.scalar(select(func.count()).select_from(JobPost))
        updated_job_post = (await db_session.execute(select(JobPost))).scalar_one()

        assert second_result.created_job_post is False
        assert second_result.job_post_id == first_result.job_post_id
        assert second_result.action == RawRecordIngestionAction.PROCESS
        assert job_post_count == 1
        assert updated_job_post.salary_text == "30-40K"
        assert updated_job_post.salary_min == 30000
        assert updated_job_post.salary_max == 40000
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_consume_raw_job_message_skips_duplicate_message_id(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        service = _build_alibaba_ingestion_service()
        message = _build_alibaba_message(
            message_id="alibaba-idempotent:message-001",
            external_job_id="ali-message-001",
            source_url="https://jobs.example.com/message-001",
            title="后端开发工程师",
            salary="20-30K",
        )

        first_result = await service.consume_raw_job_message(session=db_session, message=message)
        duplicate_result = await service.consume_raw_job_message(
            session=db_session,
            message=message.model_copy(
                update={
                    "raw_payload": {
                        **message.raw_payload,
                        "salary": "50-60K",
                    }
                }
            ),
        )
        await db_session.commit()

        raw_records = (await db_session.execute(select(RawJobRecord))).scalars().all()
        job_post = (await db_session.execute(select(JobPost))).scalar_one()

        assert first_result.action == RawRecordIngestionAction.PROCESS
        assert duplicate_result.action == RawRecordIngestionAction.DUPLICATE_MESSAGE
        assert duplicate_result.raw_record_id == first_result.raw_record_id
        assert len(raw_records) == 1
        assert raw_records[0].seen_count == 1
        assert raw_records[0].status == RawJobRecordStatus.NORMALIZED
        assert raw_records[0].raw_payload["salary"] == "20-30K"
        assert job_post.salary_text == "20-30K"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_consume_raw_job_message_skips_duplicate_raw_content_hash(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        service = _build_alibaba_ingestion_service()
        message = _build_alibaba_message(
            message_id="alibaba-idempotent:raw-001",
            external_job_id="ali-raw-001",
            source_url="https://jobs.example.com/raw-001",
            title="搜索后端工程师",
            salary="25-35K",
        )

        first_result = await service.consume_raw_job_message(session=db_session, message=message)
        duplicate_raw_result = await service.consume_raw_job_message(
            session=db_session,
            message=message.model_copy(
                update={
                    "message_id": "alibaba-idempotent:raw-002",
                    "trace_id": "trace-raw-002",
                }
            ),
        )
        await db_session.commit()

        raw_record_count = await db_session.scalar(select(func.count()).select_from(RawJobRecord))
        job_post_count = await db_session.scalar(select(func.count()).select_from(JobPost))
        raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()
        job_post = (await db_session.execute(select(JobPost))).scalar_one()

        assert first_result.action == RawRecordIngestionAction.PROCESS
        assert duplicate_raw_result.action == RawRecordIngestionAction.DUPLICATE_RAW
        assert duplicate_raw_result.raw_record_id == first_result.raw_record_id
        assert raw_record_count == 1
        assert job_post_count == 1
        assert raw_record.seen_count == 2
        assert raw_record.trace_id == "trace-raw-002"
        assert raw_record.status == RawJobRecordStatus.NORMALIZED
        assert job_post.salary_text == "25-35K"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_consume_raw_job_message_updates_same_fingerprint_with_new_raw_version(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        service = _build_alibaba_ingestion_service()
        message = _build_alibaba_message(
            message_id="alibaba-idempotent:fingerprint-001",
            external_job_id="ali-fingerprint-001",
            source_url="https://jobs.example.com/fingerprint-001",
            title="平台后端工程师",
            salary="20-30K",
            description="负责 FastAPI 后端服务建设，包含签证支持。",
        )

        first_result = await service.consume_raw_job_message(session=db_session, message=message)
        updated_result = await service.consume_raw_job_message(
            session=db_session,
            message=message.model_copy(
                update={
                    "message_id": "alibaba-idempotent:fingerprint-002",
                    "raw_payload": {
                        **message.raw_payload,
                        "salary": "30-40K",
                        "description": "",
                        "requirement": "",
                    },
                }
            ),
        )
        await db_session.commit()

        raw_record_count = await db_session.scalar(select(func.count()).select_from(RawJobRecord))
        job_post_count = await db_session.scalar(select(func.count()).select_from(JobPost))
        job_post = (await db_session.execute(select(JobPost))).scalar_one()
        detail = (await db_session.execute(select(JobPostDetail))).scalar_one()

        assert first_result.action == RawRecordIngestionAction.PROCESS
        assert updated_result.action == RawRecordIngestionAction.PROCESS
        assert updated_result.created_job_post is False
        assert updated_result.job_post_id == first_result.job_post_id
        assert raw_record_count == 2
        assert job_post_count == 1
        assert job_post.raw_record_id == updated_result.raw_record_id
        assert job_post.salary_text == "30-40K"
        assert job_post.salary_min == 30000
        assert job_post.salary_max == 40000
        assert (
            detail.description
            == "负责 FastAPI 后端服务建设，包含签证支持。\n\n本科，3-5年经验。"
        )
        assert detail.has_visa_sponsorship is True
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_ingestion_source_uses_platform_and_base_url_identity(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        social_service = RawJobIngestionService(
            source_config=JobSourceConfig(
                platform="alibaba",
                name="阿里巴巴社招",
                base_url="https://talent.taotian.com/off-campus",
            )
        )
        campus_service = RawJobIngestionService(
            source_config=JobSourceConfig(
                platform="alibaba",
                name="阿里巴巴校招",
                base_url="https://talent.taotian.com/campus",
            )
        )

        await social_service.consume_raw_job_message(
            session=db_session,
            message=_build_alibaba_message(
                message_id="alibaba-source:social",
                external_job_id="ali-social-001",
                source_url="https://talent.taotian.com/off-campus/position-detail?positionId=1",
                title="后端开发工程师",
            ),
        )
        await campus_service.consume_raw_job_message(
            session=db_session,
            message=_build_alibaba_message(
                message_id="alibaba-source:campus",
                external_job_id="ali-campus-001",
                source_url="https://talent.taotian.com/campus/position-detail?positionId=2",
                title="后端开发工程师校招",
            ),
        )
        await social_service.consume_raw_job_message(
            session=db_session,
            message=_build_alibaba_message(
                message_id="alibaba-source:social-2",
                external_job_id="ali-social-002",
                source_url="https://talent.taotian.com/off-campus/position-detail?positionId=3",
                title="搜索后端工程师",
            ),
        )
        await db_session.commit()

        sources = (
            (await db_session.execute(select(JobSource).order_by(JobSource.base_url)))
            .scalars()
            .all()
        )

        assert [(source.platform, source.name, source.base_url) for source in sources] == [
            ("alibaba", "阿里巴巴校招", "https://talent.taotian.com/campus"),
            ("alibaba", "阿里巴巴社招", "https://talent.taotian.com/off-campus"),
        ]
    finally:
        await truncate_job_tables(db_session)


def _build_alibaba_ingestion_service() -> RawJobIngestionService:
    """构造测试用阿里社招摄入服务。"""

    return RawJobIngestionService(
        source_config=JobSourceConfig(
            platform="alibaba",
            name="阿里巴巴社招",
            base_url="https://talent.taotian.com/off-campus",
        )
    )


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


def _build_alibaba_message(
    *,
    message_id: str,
    external_job_id: str,
    source_url: str,
    title: str,
    salary: str = "20-30K",
    description: str = "负责后端服务建设。",
    requirement: str = "本科，3-5年经验。",
) -> RawJobCollectedMessage:
    """构造阿里岗位消息，避免来源身份测试里重复无关字段。"""

    return RawJobCollectedMessage(
        message_id=message_id,
        source_platform="alibaba",
        external_job_id=external_job_id,
        source_url=source_url,
        producer="alijob_crawler",
        raw_payload={
            "job_id": external_job_id,
            "job_url": source_url,
            "title": title,
            "area": "杭州",
            "description": description,
            "requirement": requirement,
            "experience": "3-5年",
            "degree": "本科",
            "salary": salary,
            "publish_time": "2026-06-01",
        },
    )
