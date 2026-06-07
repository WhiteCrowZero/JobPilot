from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.enums import RawJobRecordStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.normalization import NormalizedJob
from job_pilot.modules.job_posts.enums import JobPostStatus
from job_pilot.modules.job_posts.models import (
    JobPost,
    JobPostDetail,
    JobSource,
)


def build_raw_payload_hash(raw_payload: Mapping[str, object]) -> str:
    """对 raw payload 做稳定序列化 hash，用于记录内容版本。"""

    raw = json.dumps(dict(raw_payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RawJobIngestionRepository:
    """
    原始岗位摄入相关数据库操作。

    插入重复时更新（有则更新，无则插入）
    更新部分有效字段，避免无效字段覆盖原本有效字段
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

    async def upsert_raw_record(
        self,
        *,
        db: AsyncSession,
        source_id: int,
        message: RawJobCollectedMessage,
    ) -> RawJobRecord:
        now = datetime.now(UTC)
        raw_content_hash = build_raw_payload_hash(message.raw_payload)
        insert_stmt = pg_insert(RawJobRecord).values(
            source_id=source_id,
            message_id=message.message_id,
            trace_id=message.trace_id,
            producer=message.producer,
            external_job_id=message.external_job_id,
            source_url=message.source_url,
            raw_content_hash=raw_content_hash,
            raw_payload=message.raw_payload,
            status=RawJobRecordStatus.RECEIVED,
            error_message=None,
            fetched_at=message.fetched_at,
            received_at=now,
            processed_at=None,
            first_seen_at=now,
            last_seen_at=now,
        )
        excluded = insert_stmt.excluded

        result = await db.execute(
            insert_stmt.on_conflict_do_update(
                constraint="uq_raw_job_records_message_id",
                set_={
                    "source_id": source_id,
                    "trace_id": case(
                        (func.nullif(excluded.trace_id, "").is_not(None), excluded.trace_id),
                        else_=RawJobRecord.trace_id,
                    ),
                    "producer": case(
                        (func.nullif(excluded.producer, "").is_not(None), excluded.producer),
                        else_=RawJobRecord.producer,
                    ),
                    "external_job_id": case(
                        (
                            func.nullif(excluded.external_job_id, "").is_not(None),
                            excluded.external_job_id,
                        ),
                        else_=RawJobRecord.external_job_id,
                    ),
                    "source_url": case(
                        (func.nullif(excluded.source_url, "").is_not(None), excluded.source_url),
                        else_=RawJobRecord.source_url,
                    ),
                    "raw_content_hash": raw_content_hash,
                    "raw_payload": excluded.raw_payload,
                    "status": RawJobRecordStatus.RECEIVED,
                    "error_message": None,
                    "fetched_at": case(
                        (excluded.fetched_at.is_not(None), excluded.fetched_at),
                        else_=RawJobRecord.fetched_at,
                    ),
                    "received_at": now,
                    "processed_at": None,
                    "first_seen_at": func.coalesce(RawJobRecord.first_seen_at, now),
                    "last_seen_at": now,
                    "updated_at": now,
                },
            )
            .returning(RawJobRecord)
            .execution_options(populate_existing=True)
        )
        raw_record = result.scalar_one()
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
                    "title": excluded.title,
                    "company_name": excluded.company_name,
                    "locations": excluded.locations,
                    "is_remote": excluded.is_remote,
                    "employment_type": excluded.employment_type,
                    "workplace_type": excluded.workplace_type,
                    "experience_level": excluded.experience_level,
                    "experience_min_years": excluded.experience_min_years,
                    "experience_max_years": excluded.experience_max_years,
                    "education_level": excluded.education_level,
                    "salary_text": excluded.salary_text,
                    "salary_min": excluded.salary_min,
                    "salary_max": excluded.salary_max,
                    "salary_currency": excluded.salary_currency,
                    "published_at": excluded.published_at,
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
                    "source_url": excluded.source_url,
                    "company_url": excluded.company_url,
                    "description": excluded.description,
                    "has_visa_sponsorship": excluded.has_visa_sponsorship,
                    "has_relocation_support": excluded.has_relocation_support,
                    "work_authorization_note": excluded.work_authorization_note,
                    "updated_at": now,
                },
            )
        )

    async def mark_raw_record_normalized(
        self,
        *,
        db: AsyncSession,
        raw_record: RawJobRecord,
    ) -> None:
        now = datetime.now(UTC)
        raw_record.status = RawJobRecordStatus.NORMALIZED
        raw_record.error_message = None
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
