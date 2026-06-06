from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RawJobCollectedMessage(BaseModel):
    """crawler -> RabbitMQ -> backend ingestion worker 的消息契约草稿。

    爬虫系统只需要遵守这个 raw contract，不访问后端数据库，也不写 job_posts。
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
