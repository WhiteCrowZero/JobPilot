from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import AppError, BadRequestError
from job_pilot.modules.ingestion.adapters import BaseJobAdapter, get_job_adapter
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.enums import RawJobRecordStatus
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.ingestion.normalization import NormalizedJob, normalize_job_draft
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


@dataclass(slots=True, frozen=True)
class RawJobIngestionResult:
    """单条 raw job message 消费结果，便于脚本和 worker 记录进度。"""

    raw_record_id: int
    job_post_id: int
    created_job_post: bool


@dataclass(slots=True, frozen=True)
class JobSourceConfig:
    """一次摄入任务绑定的明确来源实例。"""

    platform: str
    name: str
    base_url: str


class RawJobIngestionService:
    """
    消费原始岗位消息，并写入 raw 表和规范化岗位表。

    当前类不考虑为了消除self而把一些工具方法抽成静态方法，之后可能引入如缓存等其他依赖
    session建议每次调用单独显式传入，不做成类属性
    """

    def __init__(self, source_config: JobSourceConfig) -> None:
        self.source_config = self._normalize_source_config(source_config)

    async def consume_raw_job_message(
        self,
        *,
        session: AsyncSession,
        message: RawJobCollectedMessage,
    ) -> RawJobIngestionResult:
        self._validate_message_source(message)
        source = await self._get_or_create_source(
            db=session,
        )
        raw_record = await self._save_or_update_raw_record(
            db=session,
            source_id=source.id,
            message=message,
        )

        try:
            adapter = self._get_adapter(message.source_platform)
            draft = adapter.to_draft(message.raw_payload)
            normalized = normalize_job_draft(draft)
            job_post, created_job_post_flag = await self._upsert_job_post(
                db=session,
                source_id=source.id,
                raw_record_id=raw_record.id,
                normalized=normalized,
            )
            await self._upsert_job_post_detail(
                db=session,
                job_post_id=job_post.id,
                normalized=normalized,
            )
            await self._mark_raw_record_normalized(raw_record)
            await session.flush()
        except AppError as exc:
            await self._mark_raw_record_failed(raw_record, exc.message)
            await session.flush()
            raise
        except Exception as exc:
            await self._mark_raw_record_failed(raw_record, str(exc))
            await session.flush()
            raise

        return RawJobIngestionResult(
            raw_record_id=raw_record.id,
            job_post_id=job_post.id,
            created_job_post=created_job_post_flag,
        )

    async def _get_or_create_source(self, *, db: AsyncSession) -> JobSource:
        result = await db.execute(
            select(JobSource).where(
                JobSource.platform == self.source_config.platform,
                JobSource.base_url == self.source_config.base_url,
            )
        )
        source = result.scalar_one_or_none()
        if source is not None:
            if source.name != self.source_config.name:
                source.name = self.source_config.name
                await db.flush()
            return source

        source = JobSource(
            platform=self.source_config.platform,
            name=self.source_config.name,
            base_url=self.source_config.base_url,
            is_active=True,
        )
        db.add(source)
        await db.flush()
        return source

    def _normalize_source_config(self, source_config: JobSourceConfig) -> JobSourceConfig:
        platform = source_config.platform.strip()
        name = source_config.name.strip()
        base_url = source_config.base_url.strip().rstrip("/")

        if not platform:
            raise ValueError("source_config.platform must not be empty")
        if not name:
            raise ValueError("source_config.name must not be empty")
        if not base_url:
            raise ValueError("source_config.base_url must not be empty")

        return JobSourceConfig(platform=platform, name=name, base_url=base_url)

    def _validate_message_source(self, message: RawJobCollectedMessage) -> None:
        if message.source_platform != self.source_config.platform:
            raise BadRequestError(
                "Message source_platform does not match ingestion source config",
                code="INGESTION_SOURCE_PLATFORM_MISMATCH",
            )

    async def _save_or_update_raw_record(
        self,
        *,
        db: AsyncSession,
        source_id: int,
        message: RawJobCollectedMessage,
    ) -> RawJobRecord:
        now = datetime.now(UTC)
        raw_content_hash = build_raw_payload_hash(message.raw_payload)
        result = await db.execute(
            select(RawJobRecord).where(RawJobRecord.message_id == message.message_id)
        )
        raw_record = result.scalar_one_or_none()

        if raw_record is None:
            raw_record = RawJobRecord(
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
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(raw_record)
        else:
            raw_record.source_id = source_id
            raw_record.trace_id = message.trace_id
            raw_record.producer = message.producer
            raw_record.external_job_id = message.external_job_id
            raw_record.source_url = message.source_url
            raw_record.raw_content_hash = raw_content_hash
            raw_record.raw_payload = message.raw_payload
            raw_record.status = RawJobRecordStatus.RECEIVED
            raw_record.error_message = None
            raw_record.fetched_at = message.fetched_at
            raw_record.received_at = now
            raw_record.last_seen_at = now
            if raw_record.first_seen_at is None:
                raw_record.first_seen_at = now

        await db.flush()
        return raw_record

    def _get_adapter(self, source_platform: str) -> BaseJobAdapter:
        try:
            return get_job_adapter(source_platform)
        except KeyError as exc:
            raise BadRequestError(
                f"Unsupported job source platform: {source_platform}",
                code="UNSUPPORTED_JOB_SOURCE_PLATFORM",
            ) from exc

    async def _upsert_job_post(
        self,
        *,
        db: AsyncSession,
        source_id: int,
        raw_record_id: int,
        normalized: NormalizedJob,
    ) -> tuple[JobPost, bool]:
        now = datetime.now(UTC)
        result = await db.execute(
            select(JobPost).where(JobPost.fingerprint == normalized.fingerprint)
        )
        job_post = result.scalar_one_or_none()
        created_job_post = job_post is None

        if job_post is None:
            job_post = JobPost(
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
            db.add(job_post)
        else:
            job_post.source_id = source_id
            job_post.raw_record_id = raw_record_id
            job_post.title = normalized.title
            job_post.company_name = normalized.company_name
            job_post.locations = normalized.locations
            job_post.is_remote = normalized.is_remote
            job_post.employment_type = normalized.employment_type
            job_post.workplace_type = normalized.workplace_type
            job_post.experience_level = normalized.experience_level
            job_post.experience_min_years = normalized.experience_min_years
            job_post.experience_max_years = normalized.experience_max_years
            job_post.education_level = normalized.education_level
            job_post.salary_text = normalized.salary_text
            job_post.salary_min = normalized.salary_min
            job_post.salary_max = normalized.salary_max
            job_post.salary_currency = normalized.salary_currency
            job_post.published_at = normalized.published_at
            job_post.last_seen_at = now
            job_post.status = JobPostStatus.OPEN
            if job_post.first_seen_at is None:
                job_post.first_seen_at = now

        await db.flush()
        return job_post, created_job_post

    async def _upsert_job_post_detail(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
        normalized: NormalizedJob,
    ) -> None:
        result = await db.execute(
            select(JobPostDetail).where(JobPostDetail.job_post_id == job_post_id)
        )
        detail = result.scalar_one_or_none()

        if detail is None:
            detail = JobPostDetail(
                job_post_id=job_post_id,
                source_url=normalized.source_url,
                company_url=normalized.company_url,
                description=normalized.description,
                has_visa_sponsorship=normalized.has_visa_sponsorship,
                has_relocation_support=normalized.has_relocation_support,
                work_authorization_note=normalized.work_authorization_note,
            )
            db.add(detail)
            return

        detail.source_url = normalized.source_url
        detail.company_url = normalized.company_url
        detail.description = normalized.description
        detail.has_visa_sponsorship = normalized.has_visa_sponsorship
        detail.has_relocation_support = normalized.has_relocation_support
        detail.work_authorization_note = normalized.work_authorization_note

    async def _mark_raw_record_normalized(self, raw_record: RawJobRecord) -> None:
        now = datetime.now(UTC)
        raw_record.status = RawJobRecordStatus.NORMALIZED
        raw_record.error_message = None
        raw_record.processed_at = now
        raw_record.last_seen_at = now

    async def _mark_raw_record_failed(self, raw_record: RawJobRecord, error_message: str) -> None:
        now = datetime.now(UTC)
        raw_record.status = RawJobRecordStatus.FAILED
        raw_record.error_message = error_message[:2000]
        raw_record.processed_at = now
        raw_record.last_seen_at = now
