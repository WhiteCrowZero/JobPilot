from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, SoftDeleteMixin, TimestampMixin
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    JobPostStatus,
)

if TYPE_CHECKING:
    from job_pilot.modules.ingestion.models import RawJobRecord
    from job_pilot.modules.job_collections.models import JobCollection
    from job_pilot.modules.job_skills.models import JobPostSkill
    from job_pilot.modules.job_targets.models import JobTarget


class JobSource(TimestampMixin, Base):
    """岗位来源表。"""

    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint("platform", "base_url", name="uq_job_sources_platform_base_url"),
        {"comment": "岗位来源表，同一平台可按不同 base_url 拆分具体来源。"},
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="岗位来源主键 ID。",
    )

    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="来源平台标识，例如 alibaba、tencent。",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘。",
    )

    base_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="来源实例基础 URL，例如社招入口、校招入口或第三方职位列表页。",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        comment="该来源是否启用。",
    )

    raw_records: Mapped[list[RawJobRecord]] = relationship(
        back_populates="source",
    )

    job_posts: Mapped[list[JobPost]] = relationship(
        back_populates="source",
    )


class JobPost(TimestampMixin, SoftDeleteMixin, Base):
    """规范化岗位数据表。"""

    __tablename__ = "job_posts"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_job_posts_fingerprint"),
        Index(
            "ix_job_posts_open_published_at_id",
            text("published_at DESC NULLS LAST"),
            text("id DESC"),
            postgresql_where=text("status = 'open' AND deleted_at IS NULL"),
        ),
        Index(
            "ix_job_posts_open_created_at_id",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'open' AND deleted_at IS NULL"),
        ),
        {
            "comment": "规范化岗位热数据表，用于列表、筛选、排序和状态判断。",
        },
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="岗位主键 ID。",
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("job_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="来源 ID，关联 job_sources.id。",
    )

    raw_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_job_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="最近一次生成或更新该规范化岗位的原始记录 ID。",
    )

    fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="规范化岗位去重指纹。",
    )

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="岗位标题，用于列表展示。",
    )

    locations: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="岗位地点文本，多个地点用 / 拼接。",
    )

    experience_text: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        comment="来源岗位的经验要求文本，例如 3年以上、不限、在校生。",
    )

    education_level: Mapped[EducationLevel] = mapped_column(
        enum_column(EducationLevel, name="education_level", length=30),
        nullable=False,
        default=EducationLevel.UNKNOWN,
        server_default=EducationLevel.UNKNOWN.value,
        comment="学历等级。",
    )

    salary_text: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        comment="原始薪资文本，例如 10-15K、150-200/天。",
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="来源平台发布时间，无法解析则为空。",
    )

    status: Mapped[JobPostStatus] = mapped_column(
        enum_column(JobPostStatus, name="job_post_status", length=20),
        nullable=False,
        default=JobPostStatus.OPEN,
        server_default=JobPostStatus.OPEN.value,
        comment="规范化岗位状态。",
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="来源岗位详情 URL。",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="岗位正文。",
    )

    source: Mapped[JobSource] = relationship(
        back_populates="job_posts",
    )

    raw_record: Mapped[RawJobRecord | None] = relationship(
        back_populates="job_posts",
    )

    skill_links: Mapped[list[JobPostSkill]] = relationship(
        "JobPostSkill",
        back_populates="job_post",
        cascade="all, delete-orphan",
    )

    collections: Mapped[list[JobCollection]] = relationship(
        back_populates="job_post",
        passive_deletes=True,
    )

    targets: Mapped[list[JobTarget]] = relationship(
        back_populates="job_post",
        passive_deletes=True,
    )
