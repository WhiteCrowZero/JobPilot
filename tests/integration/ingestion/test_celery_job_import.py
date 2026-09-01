from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import ValidationError
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.enums import RawJobRecordStatus, RawJobSkillSyncStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.repository import RawRecordIngestionAction
from job_pilot.modules.ingestion.service import build_raw_job_ingestion_service
from job_pilot.modules.ingestion.sources import get_registered_job_source
from job_pilot.modules.job_posts.models import JobPost
from job_pilot.modules.job_skills.models import JobPostSkill
from job_pilot.workers.tasks.import_raw_job import execute_raw_job_import
from tests.helpers.database import truncate_job_tables
from tests.helpers.messages import build_test_raw_job_message


@pytest.mark.asyncio
async def test_execute_raw_job_import_commits_job_transaction(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        message = _build_mock_message("celery-import:first")

        result = await execute_raw_job_import(
            message_data=cast(dict[str, object], message.model_dump(mode="json")),
            task_id="task-first",
        )

        db_session.expire_all()
        raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()
        job_post = (await db_session.execute(select(JobPost))).scalar_one()
        job_skill_count = await db_session.scalar(select(func.count()).select_from(JobPostSkill))

        assert result.ingestion_action == RawRecordIngestionAction.PROCESS
        assert result.skill_sync_status == "not_started"
        assert result.matched_skill_count == 0
        assert result.unmatched_skills == []
        assert raw_record.status == RawJobRecordStatus.NORMALIZED
        assert raw_record.skill_sync_status == RawJobSkillSyncStatus.NOT_STARTED
        assert raw_record.skill_sync_error_message is None
        assert raw_record.skill_synced_at is None
        assert job_post.title == "Python Backend Engineer"
        assert job_skill_count == 0
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_execute_raw_job_import_keeps_skill_sync_deferred_for_duplicate_message(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        message = _build_mock_message("celery-import:recovery")
        source = get_registered_job_source("mock")
        ingestion_result = await build_raw_job_ingestion_service(
            source.config
        ).consume_raw_job_message(session=db_session, message=message)
        await db_session.commit()

        assert ingestion_result.job_post_id is not None
        assert (await db_session.scalar(select(func.count()).select_from(JobPostSkill))) == 0

        result = await execute_raw_job_import(
            message_data=cast(dict[str, object], message.model_dump(mode="json")),
            task_id="task-recovery",
        )

        db_session.expire_all()
        raw_record = await db_session.get(RawJobRecord, ingestion_result.raw_record_id)
        job_skill_count = await db_session.scalar(select(func.count()).select_from(JobPostSkill))

        assert raw_record is not None
        assert result.ingestion_action == RawRecordIngestionAction.DUPLICATE_MESSAGE
        assert result.skill_sync_status == "not_started"
        assert raw_record.skill_sync_status == RawJobSkillSyncStatus.NOT_STARTED
        assert job_skill_count == 0
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_execute_raw_job_import_persists_non_retryable_job_failure(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        message = _build_mock_message("celery-import:job-failure").model_copy(
            update={"raw_payload": {"title": " "}}
        )

        with pytest.raises(ValidationError):
            await execute_raw_job_import(
                message_data=cast(dict[str, object], message.model_dump(mode="json")),
                task_id="task-job-failure",
            )

        db_session.expire_all()
        raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()

        assert raw_record.status == RawJobRecordStatus.FAILED
        assert raw_record.skill_sync_status == RawJobSkillSyncStatus.NOT_STARTED
        assert raw_record.skill_sync_error_message is None
        assert raw_record.skill_synced_at is None
    finally:
        await truncate_job_tables(db_session)


def _build_mock_message(message_id: str) -> RawJobCollectedMessage:
    return build_test_raw_job_message(
        message_id=message_id,
        source_platform="mock",
        external_job_id="mock-10001",
        source_url="https://example.test/jobs/mock-10001",
        producer="jobpilot-simulator",
        raw_payload={
            "job_id": "mock-10001",
            "job_url": "https://example.test/jobs/mock-10001",
            "title": "Python Backend Engineer",
            "company": "Example",
            "location": "Remote",
            "description": "Build backend services.",
            "skills": ["Python", "FastAPI", "UnknownSkill"],
        },
    )
