from __future__ import annotations

from typing import Any, ClassVar

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.core.exceptions import ValidationError
from job_pilot.modules.ingestion.adapters import ADAPTER_REGISTRY, BaseJobAdapter, JobDraft
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.enums import RawJobRecordStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.repository import RawRecordIngestionAction
from job_pilot.modules.ingestion.service import JobSourceConfig
from job_pilot.modules.job_posts.enums import EducationLevel, ExperienceLevel, SalaryPeriod
from job_pilot.modules.job_posts.models import JobPost, JobPostDetail, JobSource
from job_pilot.modules.job_skills.models import JobPostSkill
from tests.helpers.database import truncate_job_tables


@pytest.mark.asyncio
async def test_consume_raw_job_message_normalizes_job_tables(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """原始岗位消息会通过公开入口规范化到岗位相关表。"""

    await truncate_job_tables(db_session)

    try:
        source_config = _alibaba_source_config()
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
                "skills": ["Python", "Fast API", "UnknownSkill"],
                "publish_time": "2026-06-01",
            },
        )

        first_result = await pilot.ingestion.consume_raw_job(
            source_config=source_config,
            message=message,
        )

        assert first_result.created_job_post is True
        assert [candidate.text for candidate in first_result.raw_skill_candidates] == []

        job_post = (await db_session.execute(select(JobPost))).scalar_one()
        detail = (await db_session.execute(select(JobPostDetail))).scalar_one()
        raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()
        source = (await db_session.execute(select(JobSource))).scalar_one()
        job_skills = (
            (await db_session.execute(select(JobPostSkill).order_by(JobPostSkill.skill_id)))
            .scalars()
            .all()
        )

        assert source.platform == "alibaba"
        assert source.name == "阿里巴巴社招"
        assert source.base_url == "https://talent.taotian.com/off-campus"
        assert raw_record.status == RawJobRecordStatus.NORMALIZED
        assert raw_record.external_job_id == "ali-001"
        assert raw_record.skill_content_hash is None
        assert job_post.title == "后端开发工程师"
        assert job_post.locations == "北京 / 上海 / 中国"
        assert job_post.is_remote is False
        assert job_post.salary_text == "20-30K"
        assert job_post.salary_min == 20000
        assert job_post.salary_max == 30000
        assert job_post.salary_period == SalaryPeriod.UNKNOWN
        assert job_post.experience_level == ExperienceLevel.MID
        assert job_post.education_level == EducationLevel.BACHELOR
        assert detail.description == "负责 FastAPI 后端服务建设。\n\n本科，3-5年经验。"
        assert len(job_skills) == 0

        updated_message = message.model_copy(
            update={
                "message_id": "alibaba:sample-002",
                "raw_payload": {
                    **message.raw_payload,
                    "salary": "30-40K",
                },
            }
        )
        second_result = await pilot.ingestion.consume_raw_job(
            source_config=source_config,
            message=updated_message,
        )

        job_post_count = await db_session.scalar(select(func.count()).select_from(JobPost))
        updated_job_post = (await db_session.execute(select(JobPost))).scalar_one()
        await db_session.refresh(updated_job_post)

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
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """重复 message_id 会命中摄入幂等保护。"""

    await truncate_job_tables(db_session)

    try:
        message = _build_alibaba_message(
            message_id="alibaba-idempotent:message-001",
            external_job_id="ali-message-001",
            source_url="https://jobs.example.com/message-001",
            title="后端开发工程师",
            salary="20-30K",
        )

        first_result = await pilot.ingestion.consume_raw_job(
            source_config=_alibaba_source_config(),
            message=message,
        )
        duplicate_result = await pilot.ingestion.consume_raw_job(
            source_config=_alibaba_source_config(),
            message=message.model_copy(
                update={
                    "raw_payload": {
                        **message.raw_payload,
                        "salary": "50-60K",
                    }
                }
            ),
        )

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
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """不同 message_id 但原始内容相同时按 raw hash 去重。"""

    await truncate_job_tables(db_session)

    try:
        message = _build_alibaba_message(
            message_id="alibaba-idempotent:raw-001",
            external_job_id="ali-raw-001",
            source_url="https://jobs.example.com/raw-001",
            title="搜索后端工程师",
            salary="25-35K",
        )

        first_result = await pilot.ingestion.consume_raw_job(
            source_config=_alibaba_source_config(),
            message=message,
        )
        duplicate_raw_result = await pilot.ingestion.consume_raw_job(
            source_config=_alibaba_source_config(),
            message=message.model_copy(
                update={
                    "message_id": "alibaba-idempotent:raw-002",
                    "trace_id": "trace-raw-002",
                }
            ),
        )

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
async def test_failed_raw_record_can_retry_with_same_raw_payload(
    pilot: JobPilot,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """失败 raw 再次被新消息观测到时，会重新进入清洗流程。"""

    class RetryableAdapter(BaseJobAdapter):
        source_platform: ClassVar[str] = "retry_test"
        should_fail: ClassVar[bool] = True

        def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
            _ = raw_payload
            return JobDraft(
                source_platform=self.source_platform,
                external_job_id="retry-001",
                source_url="https://jobs.example.com/retry-001",
                title="" if self.should_fail else "Retry Backend Engineer",
                company_name="Retry Tech",
                company_url=None,
                raw_location_text="Remote",
                raw_country_name=None,
                raw_city_name=None,
                raw_description="Build backend APIs.",
                raw_experience=None,
                raw_education=None,
                raw_employment_type=None,
                raw_flexibility="remote",
                raw_salary=None,
                raw_skills=[],
                published_at_raw=None,
            )

    monkeypatch.setitem(ADAPTER_REGISTRY, RetryableAdapter.source_platform, RetryableAdapter)
    await truncate_job_tables(db_session)

    try:
        source_config = JobSourceConfig(
            platform=RetryableAdapter.source_platform,
            name="Retry Jobs",
            base_url="https://jobs.example.com/retry",
        )
        message = RawJobCollectedMessage(
            message_id="retry-test:001",
            source_platform=RetryableAdapter.source_platform,
            external_job_id="retry-001",
            source_url="https://jobs.example.com/retry-001",
            producer="retry_crawler",
            raw_payload={"job_id": "retry-001"},
        )

        with pytest.raises(ValidationError):
            await pilot.ingestion.consume_raw_job(source_config=source_config, message=message)

        failed_raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()
        failed_raw_record_id = failed_raw_record.id
        failed_raw_record_status = failed_raw_record.status
        failed_raw_record_error_message = failed_raw_record.error_message
        first_job_post_count = await db_session.scalar(select(func.count()).select_from(JobPost))

        RetryableAdapter.should_fail = False
        retry_result = await pilot.ingestion.consume_raw_job(
            source_config=source_config,
            message=message.model_copy(update={"message_id": "retry-test:002"}),
        )

        db_session.expire_all()
        retried_raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()
        job_post = (await db_session.execute(select(JobPost))).scalar_one()

        assert failed_raw_record_status == RawJobRecordStatus.FAILED
        assert failed_raw_record_error_message is not None
        assert "title" in failed_raw_record_error_message
        assert first_job_post_count == 0
        assert retry_result.action == RawRecordIngestionAction.RETRY_PROCESS
        assert retry_result.raw_record_id == failed_raw_record_id
        assert retried_raw_record.status == RawJobRecordStatus.NORMALIZED
        assert retried_raw_record.seen_count == 2
        assert job_post.title == "Retry Backend Engineer"
    finally:
        RetryableAdapter.should_fail = True
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_consume_raw_job_message_updates_same_fingerprint_with_new_raw_version(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """同岗位 fingerprint 的新原始版本会更新岗位表。"""

    await truncate_job_tables(db_session)

    try:
        message = _build_alibaba_message(
            message_id="alibaba-idempotent:fingerprint-001",
            external_job_id="ali-fingerprint-001",
            source_url="https://jobs.example.com/fingerprint-001",
            title="平台后端工程师",
            salary="20-30K",
            description="负责 FastAPI 后端服务建设，包含签证支持。",
        )

        first_result = await pilot.ingestion.consume_raw_job(
            source_config=_alibaba_source_config(),
            message=message,
        )
        updated_result = await pilot.ingestion.consume_raw_job(
            source_config=_alibaba_source_config(),
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
            detail.description == "负责 FastAPI 后端服务建设，包含签证支持。\n\n本科，3-5年经验。"
        )
        assert detail.has_visa_sponsorship is True
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_consume_raw_job_message_overwrites_mobility_flags_from_new_description(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """新详情文本没有签证/搬迁信号时，允许清掉旧的 True 标记。"""

    await truncate_job_tables(db_session)

    try:
        first_message = _build_alibaba_message(
            message_id="alibaba-mobility:001",
            external_job_id="ali-mobility-001",
            source_url="https://jobs.example.com/mobility-001",
            title="平台后端工程师",
            description="负责 FastAPI 后端服务建设，包含签证支持和 relocation support。",
        )
        second_message = _build_alibaba_message(
            message_id="alibaba-mobility:002",
            external_job_id="ali-mobility-001",
            source_url="https://jobs.example.com/mobility-001",
            title="平台后端工程师",
            description="负责 FastAPI 后端服务建设。",
        )

        first_result = await pilot.ingestion.consume_raw_job(
            source_config=_alibaba_source_config(),
            message=first_message,
        )
        second_result = await pilot.ingestion.consume_raw_job(
            source_config=_alibaba_source_config(),
            message=second_message,
        )

        detail = (await db_session.execute(select(JobPostDetail))).scalar_one()

        assert second_result.job_post_id == first_result.job_post_id
        assert detail.has_visa_sponsorship is False
        assert detail.has_relocation_support is False
        assert detail.work_authorization_note is None
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_ingestion_source_uses_platform_and_base_url_identity(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """来源身份由 platform 和 base_url 区分。"""

    await truncate_job_tables(db_session)

    try:
        social_source_config = _alibaba_source_config()
        campus_source_config = JobSourceConfig(
            platform="alibaba",
            name="阿里巴巴校招",
            base_url="https://talent.taotian.com/campus",
        )

        await pilot.ingestion.consume_raw_job(
            source_config=social_source_config,
            message=_build_alibaba_message(
                message_id="alibaba-source:social",
                external_job_id="ali-social-001",
                source_url="https://talent.taotian.com/off-campus/position-detail?positionId=1",
                title="后端开发工程师",
            ),
        )
        await pilot.ingestion.consume_raw_job(
            source_config=campus_source_config,
            message=_build_alibaba_message(
                message_id="alibaba-source:campus",
                external_job_id="ali-campus-001",
                source_url="https://talent.taotian.com/campus/position-detail?positionId=2",
                title="后端开发工程师校招",
            ),
        )
        await pilot.ingestion.consume_raw_job(
            source_config=social_source_config,
            message=_build_alibaba_message(
                message_id="alibaba-source:social-2",
                external_job_id="ali-social-002",
                source_url="https://talent.taotian.com/off-campus/position-detail?positionId=3",
                title="搜索后端工程师",
            ),
        )

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


def _alibaba_source_config() -> JobSourceConfig:
    """构造测试用阿里社招来源配置。"""

    return JobSourceConfig(
        platform="alibaba",
        name="阿里巴巴社招",
        base_url="https://talent.taotian.com/off-campus",
    )


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
