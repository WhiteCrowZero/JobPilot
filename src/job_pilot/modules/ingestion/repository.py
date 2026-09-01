from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import NotFoundError, ResourceUnavailableError
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.enums import RawJobRecordStatus, RawJobSkillSyncStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.normalization import NormalizedJob
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    JobPostStatus,
)
from job_pilot.modules.job_posts.models import JobPost, JobSource


def build_raw_payload_hash(raw_payload: Mapping[str, object]) -> str:
    """对 raw payload 做稳定序列化 hash，用于记录内容版本。"""

    raw = json.dumps(dict(raw_payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RawRecordIngestionAction(StrEnum):
    """raw 消息写入后的下一步动作。"""

    PROCESS = "process"
    RETRY_PROCESS = "retry_process"
    DUPLICATE_MESSAGE = "duplicate_message"
    DUPLICATE_RAW = "duplicate_raw"


@dataclass(slots=True, frozen=True)
class RawRecordWriteResult:
    """raw 记录写入结果，供 service 决定是否进入清洗。"""

    raw_record: RawJobRecord
    action: RawRecordIngestionAction


class RawJobIngestionRepository:
    """
    原始岗位摄入相关数据库操作。

    raw 表按 message_id、source_id + raw_content_hash 分层判断幂等；
    业务岗位表按 fingerprint upsert，并尽量避免空值覆盖旧有效值。
    """

    async def get_or_create_source(
        self,
        *,
        db: AsyncSession,
        platform: str,
        name: str,
        base_url: str,
    ) -> JobSource:
        result = await db.execute(
            select(JobSource).where(
                JobSource.platform == platform,
                JobSource.base_url == base_url,
            )
        )
        source = result.scalar_one_or_none()
        if source is not None:
            if source.name != name:
                source.name = name
                await db.flush()
            return source

        source = JobSource(
            platform=platform,
            name=name,
            base_url=base_url,
            is_active=True,
        )
        db.add(source)
        await db.flush()
        return source

    async def prepare_raw_record(
        self,
        *,
        db: AsyncSession,
        source_id: int,
        message: RawJobCollectedMessage,
    ) -> RawRecordWriteResult:
        """按消息幂等和 raw 内容去重语义准备 raw 记录。"""

        now = datetime.now(UTC)

        existing_message_record = await self.get_raw_record_by_message_id(
            db=db,
            message_id=message.message_id,
        )
        if existing_message_record is not None:
            return RawRecordWriteResult(
                raw_record=existing_message_record,
                action=RawRecordIngestionAction.DUPLICATE_MESSAGE,
            )

        raw_content_hash = build_raw_payload_hash(message.raw_payload)
        existing_raw_record = await self.get_raw_record_by_source_hash(
            db=db,
            source_id=source_id,
            raw_content_hash=raw_content_hash,
        )
        if existing_raw_record is not None:
            action = (
                RawRecordIngestionAction.RETRY_PROCESS
                if existing_raw_record.status == RawJobRecordStatus.FAILED
                else RawRecordIngestionAction.DUPLICATE_RAW
            )
            return RawRecordWriteResult(
                raw_record=existing_raw_record,
                action=action,
            )

        insert_stmt = pg_insert(RawJobRecord).values(
            source_id=source_id,
            message_id=message.message_id,
            trace_id=message.trace_id,
            producer_name=message.producer,
            external_job_id=message.external_job_id,
            source_url=message.source_url,
            raw_content_hash=raw_content_hash,
            raw_payload=message.raw_payload,
            status=RawJobRecordStatus.RECEIVED,
            error_message=None,
            skill_sync_status=RawJobSkillSyncStatus.NOT_STARTED,
            skill_sync_error_message=None,
            skill_synced_at=None,
            fetched_at=message.fetched_at,
            received_at=now,
            processed_at=None,
        )
        inserted_result = await db.execute(
            insert_stmt.on_conflict_do_nothing()
            .returning(RawJobRecord)
            .execution_options(populate_existing=True)
        )
        inserted_raw_record = inserted_result.scalar_one_or_none()
        if inserted_raw_record is not None:
            return RawRecordWriteResult(
                raw_record=inserted_raw_record,
                action=RawRecordIngestionAction.PROCESS,
            )

        conflict_message_record = await self.get_raw_record_by_message_id(
            db=db,
            message_id=message.message_id,
        )
        if conflict_message_record is not None:
            return RawRecordWriteResult(
                raw_record=conflict_message_record,
                action=RawRecordIngestionAction.DUPLICATE_MESSAGE,
            )

        conflict_raw_record = await self.get_raw_record_by_source_hash(
            db=db,
            source_id=source_id,
            raw_content_hash=raw_content_hash,
        )
        if conflict_raw_record is None:
            raise ResourceUnavailableError(
                "raw_job_records insert conflict could not be classified",
                code="RAW_RECORD_CONFLICT_UNCLASSIFIED",
            )
        action = (
            RawRecordIngestionAction.RETRY_PROCESS
            if conflict_raw_record.status == RawJobRecordStatus.FAILED
            else RawRecordIngestionAction.DUPLICATE_RAW
        )
        return RawRecordWriteResult(
            raw_record=conflict_raw_record,
            action=action,
        )

    async def get_raw_record_by_message_id(
        self,
        *,
        db: AsyncSession,
        message_id: str,
    ) -> RawJobRecord | None:
        """查询同 message_id 的 raw 记录，用于 MQ 重复投递幂等。"""

        result = await db.execute(select(RawJobRecord).where(RawJobRecord.message_id == message_id))
        return result.scalar_one_or_none()

    async def get_raw_record_by_source_hash(
        self,
        *,
        db: AsyncSession,
        source_id: int,
        raw_content_hash: str,
    ) -> RawJobRecord | None:
        """查询同来源同 raw hash 的记录，用于爬虫重复内容去重。"""

        result = await db.execute(
            select(RawJobRecord).where(
                RawJobRecord.source_id == source_id,
                RawJobRecord.raw_content_hash == raw_content_hash,
            )
        )
        return result.scalar_one_or_none()

    async def get_job_post_id_by_raw_record(
        self,
        *,
        db: AsyncSession,
        raw_record_id: int,
    ) -> int | None:
        """查找当前仍关联该 raw 记录的业务岗位 ID。"""

        result = await db.execute(
            select(JobPost.id)
            .where(JobPost.raw_record_id == raw_record_id)
            .order_by(JobPost.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_skill_sync_succeeded(
        self,
        *,
        db: AsyncSession,
        raw_record_id: int,
        skipped: bool,
    ) -> None:
        """记录技能同步已完成或因无候选而正常跳过。"""

        raw_record = await self._require_raw_record(db=db, raw_record_id=raw_record_id)
        raw_record.skill_sync_status = (
            RawJobSkillSyncStatus.SKIPPED if skipped else RawJobSkillSyncStatus.SUCCEEDED
        )
        raw_record.skill_sync_error_message = None
        raw_record.skill_synced_at = datetime.now(UTC)
        await db.flush()

    async def mark_skill_sync_failed(
        self,
        *,
        db: AsyncSession,
        raw_record_id: int,
        error_message: str,
    ) -> None:
        """记录技能同步最近一次失败，供重试与人工诊断。"""

        raw_record = await self._require_raw_record(db=db, raw_record_id=raw_record_id)
        raw_record.skill_sync_status = RawJobSkillSyncStatus.FAILED
        raw_record.skill_sync_error_message = error_message[:2000]
        raw_record.skill_synced_at = None
        await db.flush()

    async def _require_raw_record(
        self,
        *,
        db: AsyncSession,
        raw_record_id: int,
    ) -> RawJobRecord:
        raw_record = await db.get(RawJobRecord, raw_record_id)
        if raw_record is None:
            raise NotFoundError(
                "Raw job record not found",
                code="RAW_JOB_RECORD_NOT_FOUND",
            )
        return raw_record

    async def upsert_job_post(
        self,
        *,
        db: AsyncSession,
        source_id: int,
        raw_record_id: int,
        normalized: NormalizedJob,
    ) -> tuple[JobPost, bool]:
        now = datetime.now(UTC)
        insert_stmt = pg_insert(JobPost).values(
            source_id=source_id,
            raw_record_id=raw_record_id,
            fingerprint=normalized.fingerprint,
            title=normalized.title,
            locations=normalized.locations,
            experience_text=normalized.experience_text,
            education_level=normalized.education_level,
            salary_text=normalized.salary_text,
            published_at=normalized.published_at,
            status=JobPostStatus.OPEN,
            source_url=normalized.source_url,
            description=normalized.description,
        )
        excluded = insert_stmt.excluded

        result = await db.execute(
            insert_stmt.on_conflict_do_update(
                constraint="uq_job_posts_fingerprint",
                set_={
                    "source_id": source_id,
                    "raw_record_id": raw_record_id,
                    "title": case(
                        (func.nullif(excluded.title, "").is_not(None), excluded.title),
                        else_=JobPost.title,
                    ),
                    "locations": case(
                        (func.nullif(excluded.locations, "").is_not(None), excluded.locations),
                        else_=JobPost.locations,
                    ),
                    "experience_text": case(
                        (
                            func.nullif(excluded.experience_text, "").is_not(None),
                            excluded.experience_text,
                        ),
                        else_=JobPost.experience_text,
                    ),
                    "education_level": case(
                        (
                            excluded.education_level != EducationLevel.UNKNOWN,
                            excluded.education_level,
                        ),
                        else_=JobPost.education_level,
                    ),
                    "salary_text": case(
                        (func.nullif(excluded.salary_text, "").is_not(None), excluded.salary_text),
                        else_=JobPost.salary_text,
                    ),
                    "source_url": case(
                        (
                            func.nullif(excluded.source_url, "").is_not(None),
                            excluded.source_url,
                        ),
                        else_=JobPost.source_url,
                    ),
                    "description": case(
                        (
                            func.nullif(excluded.description, "").is_not(None),
                            excluded.description,
                        ),
                        else_=JobPost.description,
                    ),
                    "published_at": case(
                        (excluded.published_at.is_not(None), excluded.published_at),
                        else_=JobPost.published_at,
                    ),
                    "status": JobPostStatus.OPEN,
                    "updated_at": now,
                },
            )
            .returning(JobPost, literal_column("xmax = 0").label("created_job_post"))
            .execution_options(populate_existing=True)
        )
        job_post, created_job_post = result.one()
        return job_post, bool(created_job_post)

    async def mark_raw_record_normalized(
        self,
        *,
        db: AsyncSession,
        raw_record: RawJobRecord,
    ) -> None:
        now = datetime.now(UTC)
        raw_record.status = RawJobRecordStatus.NORMALIZED
        raw_record.error_message = None
        raw_record.skill_sync_status = RawJobSkillSyncStatus.NOT_STARTED
        raw_record.skill_sync_error_message = None
        raw_record.skill_synced_at = None
        raw_record.processed_at = now
        await db.flush()

    async def mark_raw_record_failed(
        self,
        *,
        db: AsyncSession,
        raw_record: RawJobRecord,
        error_message: str,
    ) -> None:
        now = datetime.now(UTC)
        raw_record.status = RawJobRecordStatus.FAILED
        raw_record.error_message = error_message[:2000]
        raw_record.processed_at = now
        await db.flush()
