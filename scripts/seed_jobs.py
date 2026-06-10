from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_pilot.core.config import settings
from job_pilot.core.resources import build_database_only_resources
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.repository import RawJobIngestionRepository, build_raw_payload_hash
from job_pilot.modules.ingestion.service import (
    JobSourceConfig,
    RawJobIngestionService,
)

DEFAULT_MYSQL_URL = "mysql+pymysql://root:123456@127.0.0.1:3306/spider_test"

# =============================================================================
# 本地导入配置
# =============================================================================
# 可选值：alibaba / tencent / jaabz / all
IMPORT_SOURCE = "all"
# IMPORT_SOURCE = "jaabz"

# 每个来源表导入多少条数据
IMPORT_LIMIT = 1

# 来源 MySQL 数据库地址
SOURCE_MYSQL_URL = os.getenv("JOBPILOT_SOURCE_MYSQL_URL", DEFAULT_MYSQL_URL)

# 某一行导入失败时是否立刻停止
STOP_ON_ERROR = False


@dataclass(slots=True, frozen=True)
class SourceTableConfig:
    """MySQL 来源表到统一 raw job message 的字段映射。"""

    table: str
    external_id_column: str
    source_url_column: str | None
    producer: str
    source_name: str
    source_base_url: str


@dataclass(slots=True, frozen=True)
class ImportSourceResult:
    """单个来源表的导入统计。"""

    source_platform: str
    total_count: int
    success_count: int
    failed_count: int


SOURCE_TABLES: dict[str, SourceTableConfig] = {
    "alibaba": SourceTableConfig(
        table="ali_job",
        external_id_column="job_id",
        source_url_column="job_url",
        producer="alibaba_crawler",
        source_name="阿里巴巴社招",
        source_base_url="https://talent.taotian.com/off-campus",
    ),
    "tencent": SourceTableConfig(
        table="tencent_job",
        external_id_column="id",
        source_url_column=None,
        producer="tencent_crawler",
        source_name="腾讯招聘",
        source_base_url="https://careers.tencent.com",
    ),
    "jaabz": SourceTableConfig(
        table="jaabz",
        external_id_column="job_id",
        source_url_column="job_url",
        producer="jaabz_crawler",
        source_name="Jaabz",
        source_base_url="https://jaabz.com/jobs",
    ),
}


async def load_rows_from_mysql(
    *,
    mysql_url: str,
    table_name: str,
    limit: int,
) -> list[dict[str, object]]:
    """异步包装同步 pymysql 读取，避免为测试导入再引入异步 MySQL 驱动。"""

    return await asyncio.to_thread(
        _load_rows_from_mysql_sync,
        mysql_url,
        table_name,
        limit,
    )


def build_raw_job_message(
    *,
    source_platform: str,
    config: SourceTableConfig,
    row: dict[str, object],
) -> RawJobCollectedMessage:
    """把一行 MySQL 数据包装为 ingestion service 消费的 job message。"""

    raw_hash = build_raw_payload_hash(row)
    external_job_id = _text_or_none(row.get(config.external_id_column))
    source_url = (
        _text_or_none(row.get(config.source_url_column))
        if config.source_url_column is not None
        else None
    )

    return RawJobCollectedMessage(
        message_id=build_message_id(
            source_platform=source_platform,
            external_job_id=external_job_id,
            raw_hash=raw_hash,
        ),
        trace_id=f"MQ-{config.producer}",
        source_platform=source_platform,
        external_job_id=external_job_id,
        source_url=source_url,
        producer=config.producer,
        fetched_at=None,
        raw_payload=row,
    )


def build_message_id(
    *,
    source_platform: str,
    external_job_id: str | None,
    raw_hash: str,
) -> str:
    """生成不超过消息契约长度限制的稳定 message_id。"""

    message_identity = f"{source_platform}:{external_job_id or ''}:{raw_hash}"
    message_hash = build_raw_payload_hash({"message_identity": message_identity})
    return f"{source_platform[:12]}:{message_hash[:40]}"


async def import_source(
    *,
    source_platform: str,
    mysql_url: str,
    limit: int,
    session_factory: async_sessionmaker[AsyncSession],
    stop_on_error: bool,
) -> ImportSourceResult:
    """从单个 MySQL 来源表导入岗位样本。"""

    config = SOURCE_TABLES[source_platform]
    rows = await load_rows_from_mysql(
        mysql_url=mysql_url,
        table_name=config.table,
        limit=limit,
    )

    service = RawJobIngestionService(
        source_config=JobSourceConfig(
            platform=source_platform,
            name=config.source_name,
            base_url=config.source_base_url,
        ),
        repository=RawJobIngestionRepository(),
    )
    success_count = 0
    failed_count = 0

    for row in rows:
        message = build_raw_job_message(
            source_platform=source_platform,
            config=config,
            row=row,
        )

        async with session_factory() as session:
            try:
                await service.consume_raw_job_message(
                    session=session,
                    message=message,
                )
                await session.commit()
                success_count += 1
            except Exception as exc:
                failed_count += 1
                await _commit_failed_record_or_rollback(session)
                print(
                    "Failed to import "
                    f"source={source_platform}, external_job_id={message.external_job_id}; "
                    f"error={exc}"
                )
                if stop_on_error:
                    raise

    return ImportSourceResult(
        source_platform=source_platform,
        total_count=len(rows),
        success_count=success_count,
        failed_count=failed_count,
    )


async def run_import() -> list[ImportSourceResult]:
    """按全局配置运行导入流程，当前 MVP 不依赖 Redis/MQ。"""

    _validate_import_config()

    resources = build_database_only_resources(settings)
    try:
        session_factory = resources.require_database().session_factory
        results: list[ImportSourceResult] = []

        for source_platform in _selected_sources(IMPORT_SOURCE):
            result = await import_source(
                source_platform=source_platform,
                mysql_url=SOURCE_MYSQL_URL,
                limit=IMPORT_LIMIT,
                session_factory=session_factory,
                stop_on_error=STOP_ON_ERROR,
            )
            results.append(result)

            print(
                f"Imported source={result.source_platform}, total={result.total_count}, "
                f"success={result.success_count}, failed={result.failed_count}"
            )

        return results
    finally:
        await resources.close()


async def main() -> None:
    await run_import()


def _load_rows_from_mysql_sync(
    mysql_url: str,
    table_name: str,
    limit: int,
) -> list[dict[str, object]]:
    engine = create_engine(
        mysql_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    try:
        sql = text(f"SELECT * FROM `{table_name}` LIMIT :limit")
        with engine.connect() as connection:
            rows = connection.execute(sql, {"limit": limit}).mappings().all()
        return [
            {str(key): _to_json_compatible(value) for key, value in row.items()} for row in rows
        ]
    finally:
        engine.dispose()


async def _commit_failed_record_or_rollback(session: AsyncSession) -> None:
    try:
        await session.commit()
    except Exception:
        await session.rollback()


def _selected_sources(source: str) -> list[str]:
    if source == "all":
        return list(SOURCE_TABLES)
    return [source]


def _validate_import_config() -> None:
    if IMPORT_SOURCE != "all" and IMPORT_SOURCE not in SOURCE_TABLES:
        raise ValueError(
            f"Invalid IMPORT_SOURCE={IMPORT_SOURCE!r}. "
            f"Expected one of {[*SOURCE_TABLES.keys(), 'all']!r}."
        )

    if IMPORT_LIMIT <= 0:
        raise ValueError("IMPORT_LIMIT must be greater than 0.")


def _to_json_compatible(value: object) -> object:
    """把 MySQL 驱动返回的值转换成 PostgreSQL JSONB 可序列化的值。

    SQLAlchemy 写入 JSON/JSONB 时默认使用标准 JSON encoder，
    不支持 date、datetime、Decimal、bytes 等 Python 对象。
    raw_payload 是原始数据留档，适合在入库前统一转成 JSON 兼容类型。
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_to_json_compatible(item) for item in value]
    return value


def _text_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


if __name__ == "__main__":
    asyncio.run(main())
