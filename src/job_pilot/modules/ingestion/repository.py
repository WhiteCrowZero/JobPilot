from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import case, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import NotFoundError, ResourceUnavailableError
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.enums import RawJobRecordStatus, RawJobSkillSyncStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.normalization import NormalizedJob
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    JobPostStatus,
    SalaryPeriod,
    WorkplaceType,
)
from job_pilot.modules.job_posts.models import (
    JobPost,
    JobPostDetail,
    JobSource,
)


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


@dataclass(slots=True, frozen=True)
class RawSkillRebuildInput:
    """从数据库重建岗位技能候选所需的持久化输入。"""

    source_platform: str
    raw_payload: dict[str, object]


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
            await self.mark_raw_record_seen_again(
                db=db,
                raw_record=existing_raw_record,
                message=message,
                seen_at=now,
            )
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
            producer=message.producer,
            external_job_id=message.external_job_id,
            source_url=message.source_url,
            raw_content_hash=raw_content_hash,
            skill_content_hash=None,
            raw_payload=message.raw_payload,
            status=RawJobRecordStatus.RECEIVED,
            error_message=None,
            skill_sync_status=RawJobSkillSyncStatus.NOT_STARTED,
            skill_sync_error_message=None,
            skill_synced_at=None,
            fetched_at=message.fetched_at,
            received_at=now,
            processed_at=None,
            first_seen_at=now,
            last_seen_at=now,
            seen_count=1,
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
        await self.mark_raw_record_seen_again(
            db=db,
            raw_record=conflict_raw_record,
            message=message,
            seen_at=now,
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

    async def mark_raw_record_seen_again(
        self,
        *,
        db: AsyncSession,
        raw_record: RawJobRecord,
        message: RawJobCollectedMessage,
        seen_at: datetime,
    ) -> None:
        """重复 raw 内容只更新观测字段，不重置处理状态。"""

        raw_record.last_seen_at = seen_at
        raw_record.seen_count += 1
        if message.trace_id:
            raw_record.trace_id = message.trace_id
        if message.producer:
            raw_record.producer = message.producer
        if message.source_url and not raw_record.source_url:
            raw_record.source_url = message.source_url
        if message.external_job_id and not raw_record.external_job_id:
            raw_record.external_job_id = message.external_job_id
        await db.execute(
            update(JobPost)
            .where(JobPost.raw_record_id == raw_record.id)
            .values(last_seen_at=seen_at, updated_at=seen_at)
        )
        await db.flush()

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

    async def get_raw_skill_rebuild_input(
        self,
        *,
        db: AsyncSession,
        raw_record_id: int,
    ) -> RawSkillRebuildInput:
        """读取 raw payload 与来源平台，供事务二重新提取技能。"""

        result = await db.execute(
            select(JobSource.platform, RawJobRecord.raw_payload)
            .join(RawJobRecord, RawJobRecord.source_id == JobSource.id)
            .where(RawJobRecord.id == raw_record_id)
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(
                "Raw job record not found for skill synchronization",
                code="RAW_JOB_RECORD_NOT_FOUND",
            )
        source_platform, raw_payload = row
        return RawSkillRebuildInput(
            source_platform=source_platform,
            raw_payload=raw_payload,
        )

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
            company_name=normalized.company_name,
            locations=normalized.locations,
            is_remote=normalized.is_remote,
            employment_type=normalized.employment_type,
            workplace_type=normalized.workplace_type,
            experience_level=normalized.experience_level,
            experience_min_years=normalized.experience_min_years,
            experience_max_years=normalized.experience_max_years,
            education_level=normalized.education_level,
            salary_text=normalized.salary_text,
            salary_min=normalized.salary_min,
            salary_max=normalized.salary_max,
            salary_currency=normalized.salary_currency,
            salary_period=normalized.salary_period,
            published_at=normalized.published_at,
            first_seen_at=now,
            last_seen_at=now,
            status=JobPostStatus.OPEN,
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
                    "company_name": case(
                        (
                            func.nullif(excluded.company_name, "").is_not(None),
                            excluded.company_name,
                        ),
                        else_=JobPost.company_name,
                    ),
                    "locations": case(
                        (func.nullif(excluded.locations, "").is_not(None), excluded.locations),
                        else_=JobPost.locations,
                    ),
                    "is_remote": excluded.is_remote,
                    "employment_type": case(
                        (
                            excluded.employment_type != EmploymentType.UNKNOWN,
                            excluded.employment_type,
                        ),
                        else_=JobPost.employment_type,
                    ),
                    "workplace_type": case(
                        (excluded.workplace_type != WorkplaceType.UNKNOWN, excluded.workplace_type),
                        else_=JobPost.workplace_type,
                    ),
                    "experience_level": case(
                        (
                            excluded.experience_level != ExperienceLevel.UNKNOWN,
                            excluded.experience_level,
                        ),
                        else_=JobPost.experience_level,
                    ),
                    "experience_min_years": case(
                        (excluded.experience_min_years.is_not(None), excluded.experience_min_years),
                        else_=JobPost.experience_min_years,
                    ),
                    "experience_max_years": case(
                        (excluded.experience_max_years.is_not(None), excluded.experience_max_years),
                        else_=JobPost.experience_max_years,
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
                    "salary_min": case(
                        (excluded.salary_min.is_not(None), excluded.salary_min),
                        else_=JobPost.salary_min,
                    ),
                    "salary_max": case(
                        (excluded.salary_max.is_not(None), excluded.salary_max),
                        else_=JobPost.salary_max,
                    ),
                    "salary_currency": case(
                        (
                            func.nullif(excluded.salary_currency, "").is_not(None),
                            excluded.salary_currency,
                        ),
                        else_=JobPost.salary_currency,
                    ),
                    "salary_period": case(
                        (
                            excluded.salary_period != SalaryPeriod.UNKNOWN,
                            excluded.salary_period,
                        ),
                        else_=JobPost.salary_period,
                    ),
                    "published_at": case(
                        (excluded.published_at.is_not(None), excluded.published_at),
                        else_=JobPost.published_at,
                    ),
                    "first_seen_at": func.coalesce(JobPost.first_seen_at, now),
                    "last_seen_at": now,
                    "status": JobPostStatus.OPEN,
                    "updated_at": now,
                },
            )
            .returning(JobPost, literal_column("xmax = 0").label("created_job_post"))
            .execution_options(populate_existing=True)
        )
        job_post, created_job_post = result.one()
        return job_post, bool(created_job_post)

    async def upsert_job_post_detail(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
        normalized: NormalizedJob,
    ) -> None:
        now = datetime.now(UTC)
        insert_stmt = pg_insert(JobPostDetail).values(
            job_post_id=job_post_id,
            source_url=normalized.source_url,
            company_url=normalized.company_url,
            description=normalized.description,
            has_visa_sponsorship=normalized.has_visa_sponsorship,
            has_relocation_support=normalized.has_relocation_support,
            work_authorization_note=normalized.work_authorization_note,
        )
        excluded = insert_stmt.excluded

        await db.execute(
            insert_stmt.on_conflict_do_update(
                index_elements=[JobPostDetail.job_post_id],
                set_={
                    "source_url": case(
                        (func.nullif(excluded.source_url, "").is_not(None), excluded.source_url),
                        else_=JobPostDetail.source_url,
                    ),
                    "company_url": case(
                        (func.nullif(excluded.company_url, "").is_not(None), excluded.company_url),
                        else_=JobPostDetail.company_url,
                    ),
                    "description": case(
                        (func.nullif(excluded.description, "").is_not(None), excluded.description),
                        else_=JobPostDetail.description,
                    ),
                    "has_visa_sponsorship": case(
                        (
                            excluded.has_visa_sponsorship.is_not(None),
                            excluded.has_visa_sponsorship,
                        ),
                        else_=JobPostDetail.has_visa_sponsorship,
                    ),
                    "has_relocation_support": case(
                        (
                            excluded.has_relocation_support.is_not(None),
                            excluded.has_relocation_support,
                        ),
                        else_=JobPostDetail.has_relocation_support,
                    ),
                    "work_authorization_note": case(
                        (
                            func.nullif(excluded.work_authorization_note, "").is_not(None),
                            excluded.work_authorization_note,
                        ),
                        else_=JobPostDetail.work_authorization_note,
                    ),
                    "updated_at": now,
                },
            )
        )

    async def mark_raw_record_normalized(
        self,
        *,
        db: AsyncSession,
        raw_record: RawJobRecord,
        skill_content_hash: str | None,
    ) -> None:
        now = datetime.now(UTC)
        raw_record.status = RawJobRecordStatus.NORMALIZED
        raw_record.error_message = None
        raw_record.skill_content_hash = skill_content_hash
        raw_record.skill_sync_status = RawJobSkillSyncStatus.PENDING
        raw_record.skill_sync_error_message = None
        raw_record.skill_synced_at = None
        raw_record.processed_at = now
        raw_record.last_seen_at = now
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
        raw_record.last_seen_at = now
        await db.flush()
