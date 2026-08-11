from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.search import SqlLikeSearchBackend
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.enums import RawJobRecordStatus, RawJobSkillSyncStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.repository import RawRecordIngestionAction
from job_pilot.modules.ingestion.service import build_raw_job_ingestion_service
from job_pilot.modules.ingestion.sources import get_registered_job_source
from job_pilot.modules.job_posts.models import JobPost
from job_pilot.modules.job_skills.contracts import RawSkillCandidate, SkillSyncResult
from job_pilot.modules.job_skills.models import JobPostSkill
from job_pilot.modules.job_skills.repository import SkillDictionaryRepository
from job_pilot.workers.tasks.import_raw_job import execute_raw_job_import
from tests.helpers.database import truncate_job_tables
from tests.helpers.messages import build_test_raw_job_message


@pytest.mark.asyncio
async def test_execute_raw_job_import_commits_job_and_skill_transactions(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        await _seed_skill_dictionary(db_session)
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
        assert result.matched_skill_count == 2
        assert result.unmatched_skills == ["UnknownSkill"]
        assert raw_record.status == RawJobRecordStatus.NORMALIZED
        assert raw_record.skill_sync_status == RawJobSkillSyncStatus.SUCCEEDED
        assert raw_record.skill_sync_error_message is None
        assert raw_record.skill_synced_at is not None
        assert job_post.title == "Python Backend Engineer"
        assert job_skill_count == 2
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_execute_raw_job_import_rebuilds_skills_after_transaction_one_committed(
    db_session: AsyncSession,
) -> None:
    await truncate_job_tables(db_session)

    try:
        await _seed_skill_dictionary(db_session)
        message = _build_mock_message("celery-import:recovery")
        source = get_registered_job_source("mock")
        ingestion_result = await build_raw_job_ingestion_service(
            source.config
        ).consume_raw_job_message(session=db_session, message=message)
        await db_session.commit()

        assert ingestion_result.job_post_id is not None
        assert (
            await db_session.scalar(select(func.count()).select_from(JobPostSkill))
        ) == 0

        result = await execute_raw_job_import(
            message_data=cast(dict[str, object], message.model_dump(mode="json")),
            task_id="task-recovery",
        )

        db_session.expire_all()
        raw_record = await db_session.get(RawJobRecord, ingestion_result.raw_record_id)
        job_skill_count = await db_session.scalar(select(func.count()).select_from(JobPostSkill))

        assert raw_record is not None
        assert result.ingestion_action == RawRecordIngestionAction.DUPLICATE_MESSAGE
        assert raw_record.skill_sync_status == RawJobSkillSyncStatus.SUCCEEDED
        assert job_skill_count == 2
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_execute_raw_job_import_persists_non_retryable_skill_failure(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingSkillSyncService:
        async def sync_from_raw_candidates(
            self,
            *,
            db: AsyncSession,
            job_post_id: int,
            candidates: list[RawSkillCandidate],
        ) -> SkillSyncResult:
            _ = db, job_post_id, candidates
            raise ValueError("fixed skill mapping failure")

    await truncate_job_tables(db_session)
    monkeypatch.setattr(
        "job_pilot.workers.tasks.import_raw_job.build_job_skill_sync_service",
        lambda _search_backend: FailingSkillSyncService(),
    )

    try:
        message = _build_mock_message("celery-import:skill-failure")

        with pytest.raises(ValueError, match="fixed skill mapping failure"):
            await execute_raw_job_import(
                message_data=cast(dict[str, object], message.model_dump(mode="json")),
                task_id="task-skill-failure",
            )

        db_session.expire_all()
        raw_record = (await db_session.execute(select(RawJobRecord))).scalar_one()

        assert raw_record.status == RawJobRecordStatus.NORMALIZED
        assert raw_record.skill_sync_status == RawJobSkillSyncStatus.FAILED
        assert raw_record.skill_sync_error_message == "fixed skill mapping failure"
        assert raw_record.skill_synced_at is None
    finally:
        await truncate_job_tables(db_session)


async def _seed_skill_dictionary(session: AsyncSession) -> None:
    repository = SkillDictionaryRepository(SqlLikeSearchBackend())
    for skill_name, aliases in [
        ("Python", ["python"]),
        ("FastAPI", ["fastapi"]),
    ]:
        skill, _ = await repository.upsert_skill(db=session, name=skill_name)
        for alias in aliases:
            await repository.upsert_alias(db=session, skill_id=skill.id, alias=alias)
    await session.commit()


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
