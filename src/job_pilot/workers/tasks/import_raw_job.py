from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import asdict, dataclass

from celery import Task
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as SqlAlchemyTimeoutError

from job_pilot.core.config import settings
from job_pilot.core.exceptions import AppError
from job_pilot.core.logging import log_app_event
from job_pilot.db.session import build_database_resource
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.service import build_raw_job_ingestion_service
from job_pilot.modules.ingestion.sources import get_registered_job_source
from job_pilot.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

MAX_IMPORT_RETRIES = 5
MAX_RETRY_COUNTDOWN_SECONDS = 60
RETRYABLE_SQLSTATES = {
    "08000",
    "08003",
    "08006",
    "40001",
    "40P01",
    "53300",
    "57P01",
}


@dataclass(slots=True, frozen=True)
class RawJobImportTaskResult:
    """岗位完整摄入任务的 JSON 结果。"""

    raw_record_id: int
    job_post_id: int | None
    ingestion_action: str
    skill_sync_status: str
    matched_skill_count: int
    unmatched_skills: list[str]


@celery_app.task(bind=True, name="job.import_raw", max_retries=MAX_IMPORT_RETRIES)
def import_raw_job(self: Task, message_data: dict[str, object]) -> dict[str, object]:
    """消费一条岗位消息并完成岗位主数据导入。"""

    try:
        result = asyncio.run(
            execute_raw_job_import(
                message_data=message_data,
                task_id=str(self.request.id or "unknown"),
            )
        )
    except Exception as exc:
        correlation = build_log_correlation(
            message_data=message_data,
            task_id=str(self.request.id or "unknown"),
            raw_record_id=getattr(exc, "raw_record_id", None),
        )
        if not is_retryable_ingestion_error(exc):
            logger.warning(
                "Raw job import failed without retry",
                extra={**correlation, "error_type": type(exc).__name__},
            )
            raise
        countdown = build_retry_countdown(self.request.retries)
        logger.warning(
            "Raw job import scheduled for retry",
            extra={
                **correlation,
                "retry_count": self.request.retries,
                "countdown_seconds": countdown,
                "error_type": type(exc).__name__,
            },
        )
        raise self.retry(exc=exc, countdown=countdown) from exc
    return asdict(result)


async def execute_raw_job_import(
    *,
    message_data: dict[str, object],
    task_id: str,
) -> RawJobImportTaskResult:
    """执行可测试的异步岗位导入编排。"""

    message = RawJobCollectedMessage.model_validate(message_data)
    registered_source = get_registered_job_source(message.source_platform)
    database = build_database_resource(settings)
    raw_record_id: int | None = None

    try:
        ingestion_service = build_raw_job_ingestion_service(registered_source.config)
        async with database.session_factory() as session:
            try:
                ingestion_result = await ingestion_service.consume_raw_job_message(
                    session=session,
                    message=message,
                )
                raw_record_id = ingestion_result.raw_record_id
                await session.commit()
            except Exception as exc:
                if is_retryable_ingestion_error(exc):
                    await session.rollback()
                else:
                    await session.commit()
                raise

        log_app_event(
            logger,
            "Raw job import completed",
            extra={
                "task_id": task_id,
                "trace_id": message.trace_id,
                "message_id": message.message_id,
                "raw_record_id": ingestion_result.raw_record_id,
                "job_post_id": ingestion_result.job_post_id,
                "ingestion_action": ingestion_result.action.value,
                "skill_sync_status": "not_started",
            },
        )
        return RawJobImportTaskResult(
            raw_record_id=ingestion_result.raw_record_id,
            job_post_id=ingestion_result.job_post_id,
            ingestion_action=ingestion_result.action.value,
            skill_sync_status="not_started",
            matched_skill_count=0,
            unmatched_skills=[],
        )
    except (PydanticValidationError, AppError):
        logger.warning(
            "Raw job import rejected without retry",
            extra={
                "task_id": task_id,
                "trace_id": message.trace_id,
                "message_id": message.message_id,
                "raw_record_id": raw_record_id,
                "error_type": "contract_or_business_error",
            },
        )
        raise
    except Exception as exc:
        if raw_record_id is not None:
            try:
                exc.__dict__["raw_record_id"] = raw_record_id
            except (AttributeError, TypeError):
                pass
        raise
    finally:
        await database.close()


def is_retryable_ingestion_error(exc: BaseException) -> bool:
    """只允许连接、超时、死锁和事务序列化类基础设施错误重试。"""

    if isinstance(exc, (OperationalError, InterfaceError, SqlAlchemyTimeoutError)):
        return True
    if not isinstance(exc, DBAPIError):
        return False
    if exc.connection_invalidated:
        return True
    sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
    return sqlstate in RETRYABLE_SQLSTATES


def build_retry_countdown(retry_count: int) -> int:
    """计算带少量 jitter 的有界指数退避秒数。"""

    base = min(2 ** max(retry_count, 0), MAX_RETRY_COUNTDOWN_SECONDS)
    jitter = random.uniform(0, max(base * 0.2, 1))
    return min(int(base + jitter), MAX_RETRY_COUNTDOWN_SECONDS)


def build_log_correlation(
    *,
    message_data: dict[str, object],
    task_id: str,
    raw_record_id: object | None,
) -> dict[str, object | None]:
    """只提取安全标识用于 Worker 日志，禁止携带 raw payload。"""

    return {
        "task_id": task_id,
        "trace_id": message_data.get("trace_id"),
        "message_id": message_data.get("message_id"),
        "raw_record_id": raw_record_id,
    }
