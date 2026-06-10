from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import AppError, BadRequestError
from job_pilot.modules.ingestion.adapters import BaseJobAdapter, get_job_adapter
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.normalization import normalize_job_draft
from job_pilot.modules.ingestion.normalization.skills import (
    build_skill_content_hash,
    extract_raw_skill_candidates,
)
from job_pilot.modules.ingestion.repository import (
    RawJobIngestionRepository,
    RawRecordIngestionAction,
)
from job_pilot.modules.job_skills.skill_sync_contracts import RawSkillCandidate

logger = logging.getLogger(__name__)

# TODO：之后引入MQ和Celery处理消息


@dataclass(slots=True, frozen=True)
class RawJobIngestionResult:
    """单条 raw job message 消费结果，便于脚本和 worker 记录进度。"""

    raw_record_id: int
    job_post_id: int | None
    created_job_post: bool
    action: RawRecordIngestionAction
    raw_skill_candidates: list[RawSkillCandidate]
    skill_content_hash: str | None


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

    def __init__(
        self,
        source_config: JobSourceConfig,
        repository: RawJobIngestionRepository,
    ) -> None:
        self.source_config = self._normalize_source_config(source_config)
        self.repository = repository

    async def consume_raw_job_message(
        self,
        *,
        session: AsyncSession,
        message: RawJobCollectedMessage,
    ) -> RawJobIngestionResult:
        self._validate_message_source(message)
        source = await self.repository.get_or_create_source(
            db=session,
            platform=self.source_config.platform,
            name=self.source_config.name,
            base_url=self.source_config.base_url,
        )
        raw_record_result = await self.repository.prepare_raw_record(
            db=session,
            source_id=source.id,
            message=message,
        )
        raw_record = raw_record_result.raw_record

        if raw_record_result.action != RawRecordIngestionAction.PROCESS:
            job_post_id = await self.repository.get_job_post_id_by_raw_record(
                db=session,
                raw_record_id=raw_record.id,
            )
            logger.info(
                "Raw job message skipped by ingestion idempotency",
                extra={
                    "source_platform": message.source_platform,
                    "external_job_id": message.external_job_id,
                    "message_id": message.message_id,
                    "raw_record_id": raw_record.id,
                    "action": raw_record_result.action,
                },
            )
            await session.commit()
            return RawJobIngestionResult(
                raw_record_id=raw_record.id,
                job_post_id=job_post_id,
                created_job_post=False,
                action=raw_record_result.action,
                raw_skill_candidates=[],
                skill_content_hash=raw_record.skill_content_hash,
            )

        try:
            adapter = self._get_adapter(message.source_platform)
            draft = adapter.to_draft(message.raw_payload)
            raw_skill_candidates = extract_raw_skill_candidates(draft.raw_skills)
            skill_content_hash = build_skill_content_hash(raw_skill_candidates)
            normalized = normalize_job_draft(draft)
            job_post, created_job_post_flag = await self.repository.upsert_job_post(
                db=session,
                source_id=source.id,
                raw_record_id=raw_record.id,
                normalized=normalized,
            )
            await self.repository.upsert_job_post_detail(
                db=session,
                job_post_id=job_post.id,
                normalized=normalized,
            )
            await self.repository.mark_raw_record_normalized(
                db=session,
                raw_record=raw_record,
                skill_content_hash=skill_content_hash,
            )
            await session.commit()
        except AppError as exc:
            await self.repository.mark_raw_record_failed(
                db=session,
                raw_record=raw_record,
                error_message=exc.message,
            )
            await session.commit()
            logger.warning(
                "Raw job message failed business validation",
                extra={
                    "source_platform": message.source_platform,
                    "external_job_id": message.external_job_id,
                    "message_id": message.message_id,
                    "raw_record_id": raw_record.id,
                    "error_code": exc.code,
                },
            )
            raise
        except Exception as exc:
            await self.repository.mark_raw_record_failed(
                db=session,
                raw_record=raw_record,
                error_message=str(exc),
            )
            await session.commit()
            logger.exception(
                "Raw job message failed during normalization",
                extra={
                    "source_platform": message.source_platform,
                    "external_job_id": message.external_job_id,
                    "message_id": message.message_id,
                    "raw_record_id": raw_record.id,
                },
            )
            raise

        return RawJobIngestionResult(
            raw_record_id=raw_record.id,
            job_post_id=job_post.id,
            created_job_post=created_job_post_flag,
            action=RawRecordIngestionAction.PROCESS,
            raw_skill_candidates=raw_skill_candidates,
            skill_content_hash=skill_content_hash,
        )

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

    def _get_adapter(self, source_platform: str) -> BaseJobAdapter:
        try:
            return get_job_adapter(source_platform)
        except KeyError as exc:
            raise BadRequestError(
                f"Unsupported job source platform: {source_platform}",
                code="UNSUPPORTED_JOB_SOURCE_PLATFORM",
            ) from exc


def build_raw_job_ingestion_service(source_config: JobSourceConfig) -> RawJobIngestionService:
    """组装 raw job 摄入 service 的默认依赖。"""

    return RawJobIngestionService(
        source_config=source_config,
        repository=RawJobIngestionRepository(),
    )
