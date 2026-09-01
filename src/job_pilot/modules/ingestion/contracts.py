from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

"""
数据处理流程：

爬虫原始数据
  -> 包装成 message
-----
MQ 解耦爬虫和后端
-----
后端数据导入（与清洗）
  -> adapters
  -> 中间草稿结构 draft
  -> normalize
  -> 后端业务表结构

其中，MQ是业务上的解耦层，draft是数据上的解耦层
- adapter 负责“外部爬虫数据 → 内部 Draft”
- normalize 负责“Draft → 后端业务结构 / 入库结构”
"""


class RawJobCollectedMessage(BaseModel):
    """crawler -> RabbitMQ -> backend ingestion worker 的消息契约。

    爬虫系统只需要遵守这个 raw contract，不访问后端数据库。
    后端收到后负责保存 raw_job_records，并调用 adapter + normalizer。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    event_type: Literal["job.raw.collected"]
    message_id: str = Field(min_length=36, max_length=36)
    trace_id: str = Field(min_length=36, max_length=36)

    source_platform: str = Field(min_length=1, max_length=50)
    external_job_id: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=1000)

    producer: str = Field(min_length=1, max_length=100)
    fetched_at: datetime

    raw_payload: dict[str, JsonValue]

    @field_validator("message_id", "trace_id")
    @classmethod
    def validate_uuid_text(cls, value: str) -> str:
        """校验并规范化消息和追踪 UUID。"""

        return str(UUID(value))

    @field_validator("fetched_at")
    @classmethod
    def validate_timezone_aware_datetime(cls, value: datetime | None) -> datetime | None:
        """消息时间必须包含明确时区，避免跨进程解释不一致。"""

        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("message datetime must be timezone-aware")
        return value

    @field_validator("source_platform", "external_job_id", "source_url", "producer")
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        """去除契约文本边界空白，并拒绝只有空白的值。"""

        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("message text field must not be blank")
        return stripped

    @model_validator(mode="after")
    def validate_source_identity(self) -> RawJobCollectedMessage:
        """每条来源消息至少携带一个稳定岗位定位字段。"""

        if self.external_job_id is None and self.source_url is None:
            raise ValueError("external_job_id or source_url is required")
        return self
