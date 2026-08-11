from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, TimestampMixin
from job_pilot.modules.ingestion.enums import RawJobRecordStatus, RawJobSkillSyncStatus

if TYPE_CHECKING:
    from job_pilot.modules.job_posts.models import JobPost, JobSource


class RawJobRecord(TimestampMixin, Base):
    """原始岗位记录表。

    这是 crawler / 文件导入 / RabbitMQ 与后端 normalized tables 的边界表。
    爬虫只推 raw message，不访问后端数据库，不写 job_posts，不决定统一枚举；
    后端 ingestion worker 保存 raw，然后调用 adapter + normalizer 生成 job_posts/details/locations。
    """

    __tablename__ = "raw_job_records"
    __table_args__ = (
        Index(
            "uq_raw_job_records_message_id",
            "message_id",
            unique=True,
            postgresql_where=text("message_id IS NOT NULL"),
        ),
        UniqueConstraint(
            "source_id",
            "raw_content_hash",
            name="uq_raw_job_records_source_hash",
        ),
        {
            "comment": "原始岗位记录表，保存爬虫或文件导入推来的 raw payload。",
        },
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="原始岗位记录主键 ID。",
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("job_sources.id", ondelete="RESTRICT"),
        nullable=False,
        comment="来源 ID，关联 job_sources.id。",
    )

    # RabbitMQ / crawler message contract fields. File import can leave them NULL.
    message_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="消息唯一 ID。RabbitMQ 模式下用于幂等；文件导入可为空。",
    )

    trace_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="链路追踪 ID，用于串联 crawler、MQ、ingestion worker 日志。",
    )

    producer: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="生产者名称，例如 alibaba-crawler、excel-importer。",
    )

    external_job_id: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        comment="来源平台自己的岗位 ID。只放 raw 表，不放 job_posts 主表。",
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="来源岗位详情 URL。规范化详情表可冗余一份用于展示。",
    )

    raw_content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="raw_payload 规范化序列化后的内容 hash，用于幂等和变化检测。",
    )

    skill_content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="raw_payload 中结构化技能候选内容的 hash，用于追踪技能字段变化。",
    )

    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="来源原始字段，PostgreSQL JSONB。",
    )

    status: Mapped[RawJobRecordStatus] = mapped_column(
        enum_column(RawJobRecordStatus, name="raw_job_record_status", length=30),
        nullable=False,
        default=RawJobRecordStatus.RECEIVED,
        server_default=RawJobRecordStatus.RECEIVED.value,
        comment="原始记录处理状态。",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="adapter/normalizer 失败时记录错误原因。",
    )

    skill_sync_status: Mapped[RawJobSkillSyncStatus] = mapped_column(
        enum_column(RawJobSkillSyncStatus, name="raw_job_skill_sync_status", length=30),
        nullable=False,
        default=RawJobSkillSyncStatus.NOT_STARTED,
        server_default=RawJobSkillSyncStatus.NOT_STARTED.value,
        comment="岗位技能同步状态，与 raw 规范化状态分开记录。",
    )

    skill_sync_error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="最近一次失败原因。",
    )

    skill_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="技能同步成功或确认跳过时间。",
    )

    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="爬虫采集到该原始记录的时间，文件导入可为空。",
    )

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="后端收到该原始记录的时间。",
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="后端完成规范化处理的时间。",
    )

    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="系统第一次看到该来源记录的时间。",
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="系统最近一次看到该来源记录的时间。",
    )

    seen_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="同一来源 raw 内容被重复看到的次数。",
    )

    source: Mapped[JobSource] = relationship(
        back_populates="raw_records",
    )

    job_posts: Mapped[list[JobPost]] = relationship(
        back_populates="raw_record",
    )
