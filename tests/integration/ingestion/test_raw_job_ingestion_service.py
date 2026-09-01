from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.ingestion.enums import RawJobRecordStatus, RawJobSkillSyncStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.repository import RawRecordIngestionAction
from job_pilot.modules.ingestion.service import JobSourceConfig
from job_pilot.modules.job_posts.enums import EducationLevel
from job_pilot.modules.job_posts.models import JobPost, JobSource
from tests.helpers.database import truncate_job_tables
from tests.helpers.messages import build_test_raw_job_message, stable_test_uuid


@pytest.mark.asyncio
async def test_consume_raw_job_message_normalizes_confirmed_job_fields(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """raw 消息会写入原始记录并生成已确认结构的岗位主数据。"""

    await truncate_job_tables(db_session)
    try:
        message = _build_taotian_message(
            message_id="taotian:sample-001",
            salary="20-30K",
        )

        result = await pilot.ingestion.consume_raw_job(
            source_config=_taotian_source_config(),
            message=message,
        )

        source = (await db_session.execute(select(JobSource))).scalar_one()
        raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()
        job_post = (await db_session.execute(select(JobPost))).scalar_one()

        assert result.created_job_post is True
        assert result.action == RawRecordIngestionAction.PROCESS
        assert source.platform == "taotian"
        assert raw_record.producer_name == "taotian_crawler"
        assert raw_record.status == RawJobRecordStatus.NORMALIZED
        assert raw_record.skill_sync_status == RawJobSkillSyncStatus.NOT_STARTED
        assert job_post.title == "后端开发工程师"
        assert job_post.locations == "北京/上海"
        assert job_post.experience_text == "3-5年"
        assert job_post.education_level == EducationLevel.BACHELOR
        assert job_post.salary_text == "20-30K"
        assert job_post.source_url == "https://jobs.example.com/ali-001"
        assert job_post.description == "负责 FastAPI 后端服务建设。\n\n本科，3-5年经验。"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_new_raw_content_updates_existing_fingerprinted_job(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """同一来源岗位的新 raw 内容创建新 raw 记录并更新同一 JobPost。"""

    await truncate_job_tables(db_session)
    try:
        first_message = _build_taotian_message(
            message_id="taotian:update-001",
            salary="20-30K",
        )
        first_result = await pilot.ingestion.consume_raw_job(
            source_config=_taotian_source_config(),
            message=first_message,
        )
        second_result = await pilot.ingestion.consume_raw_job(
            source_config=_taotian_source_config(),
            message=first_message.model_copy(
                update={
                    "message_id": stable_test_uuid("taotian:update-002"),
                    "raw_payload": {**first_message.raw_payload, "salary": "30-40K"},
                }
            ),
        )

        raw_count = await db_session.scalar(select(func.count()).select_from(RawJobRecord))
        job_count = await db_session.scalar(select(func.count()).select_from(JobPost))
        job_post = (await db_session.execute(select(JobPost))).scalar_one()

        assert first_result.created_job_post is True
        assert second_result.created_job_post is False
        assert second_result.job_post_id == first_result.job_post_id
        assert raw_count == 2
        assert job_count == 1
        assert job_post.salary_text == "30-40K"
        assert job_post.raw_record_id == second_result.raw_record_id
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_duplicate_message_keeps_original_raw_record_immutable(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """重复 message_id 只返回原记录，不覆盖原始 payload。"""

    await truncate_job_tables(db_session)
    try:
        message = _build_taotian_message(
            message_id="taotian:duplicate-message",
            salary="20-30K",
        )
        first_result = await pilot.ingestion.consume_raw_job(
            source_config=_taotian_source_config(),
            message=message,
        )
        duplicate_result = await pilot.ingestion.consume_raw_job(
            source_config=_taotian_source_config(),
            message=message.model_copy(
                update={"raw_payload": {**message.raw_payload, "salary": "50-60K"}}
            ),
        )

        raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()
        job_post = (await db_session.execute(select(JobPost))).scalar_one()

        assert duplicate_result.action == RawRecordIngestionAction.DUPLICATE_MESSAGE
        assert duplicate_result.raw_record_id == first_result.raw_record_id
        assert raw_record.raw_payload["salary"] == "20-30K"
        assert job_post.salary_text == "20-30K"
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_duplicate_raw_content_keeps_original_observation(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """不同消息携带相同 raw 内容时按 source + raw hash 去重。"""

    await truncate_job_tables(db_session)
    try:
        message = _build_taotian_message(
            message_id="taotian:duplicate-raw-001",
            salary="25-35K",
        )
        first_result = await pilot.ingestion.consume_raw_job(
            source_config=_taotian_source_config(),
            message=message,
        )
        duplicate_result = await pilot.ingestion.consume_raw_job(
            source_config=_taotian_source_config(),
            message=message.model_copy(
                update={
                    "message_id": stable_test_uuid("taotian:duplicate-raw-002"),
                    "trace_id": stable_test_uuid("trace:duplicate-raw-002"),
                }
            ),
        )

        raw_records = (await db_session.execute(select(RawJobRecord))).scalars().all()

        assert duplicate_result.action == RawRecordIngestionAction.DUPLICATE_RAW
        assert duplicate_result.raw_record_id == first_result.raw_record_id
        assert len(raw_records) == 1
        assert raw_records[0].message_id == message.message_id
        assert raw_records[0].trace_id == message.trace_id
    finally:
        await truncate_job_tables(db_session)


def _taotian_source_config() -> JobSourceConfig:
    return JobSourceConfig(
        platform="taotian",
        name="淘天招聘",
        base_url="https://talent.taotian.com",
    )


def _build_taotian_message(*, message_id: str, salary: str):
    return build_test_raw_job_message(
        message_id=message_id,
        source_platform="taotian",
        external_job_id="ali-001",
        source_url="https://jobs.example.com/ali-001",
        producer="taotian_crawler",
        raw_payload={
            "title": "后端开发工程师",
            "area": "北京/上海",
            "description": "负责 FastAPI 后端服务建设。",
            "requirement": "本科，3-5年经验。",
            "experience": "3-5年",
            "degree": "本科",
            "salary": salary,
            "publish_time": "2026-06-01",
        },
    )
