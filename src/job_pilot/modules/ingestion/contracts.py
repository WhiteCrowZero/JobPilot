from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
- 中间的 draft 尽可能稳定，更好的承担解耦职责
"""


class RawJobCollectedMessage(BaseModel):
    """crawler -> RabbitMQ -> backend ingestion worker 的消息契约草稿。

    爬虫系统只需要遵守这个 raw contract，不访问后端数据库。
    后端收到后负责保存 raw_job_records，并调用 adapter + normalizer。
    """

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(default="job.raw.collected")
    message_id: str = Field(min_length=1, max_length=64)
    trace_id: str | None = Field(default=None, max_length=64)

    source_platform: str = Field(min_length=1, max_length=50)
    external_job_id: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=1000)

    producer: str | None = Field(default=None, max_length=100)
    fetched_at: datetime | None = None

    raw_payload: dict[str, Any]
