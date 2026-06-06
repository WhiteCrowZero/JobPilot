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
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, SoftDeleteMixin, TimestampMixin
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    JobPostStatus,
    WorkplaceType,
)

if TYPE_CHECKING:
    from job_pilot.modules.ingestion.models import RawJobRecord


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
        comment="来源平台标识，例如 alibaba、tencent、jaabz；同平台可有多个来源实例。",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘、Jaabz。",
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
    """规范化岗位热数据表。

    MVP 阶段只保留查询真正需要的热字段。
    地点不再拆单独表：locations 保存来源地点文本，is_remote 提供远程筛选。
    正文、来源 URL、公司 URL、签证/搬迁等低频冷数据放 job_post_details。
    """

    __tablename__ = "job_posts"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_job_posts_fingerprint"),
        Index("ix_job_posts_source_id", "source_id"),
        Index("ix_job_posts_raw_record_id", "raw_record_id"),
        Index("ix_job_posts_status_published_at", "status", "published_at"),
        Index("ix_job_posts_status_created_at", "status", "created_at"),
        Index("ix_job_posts_is_remote", "is_remote"),
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
        comment="来源 ID，关联 job_sources.id。",
    )

    raw_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_job_records.id", ondelete="SET NULL"),
        nullable=True,
        comment="最近一次生成或更新该规范化岗位的原始记录 ID。",
    )

    fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="规范化岗位去重指纹。数据库唯一约束兜底防重。",
    )

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="岗位标题，用于列表展示。MVP 使用 ILIKE，后续可接 ES/embedding。",
    )

    company_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="公司名称。MVP 不单独拆 companies 表。",
    )

    locations: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="岗位地点文本，多个地点用 / 拼接。MVP 不拆国家、城市、区域表。",
    )

    is_remote: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="是否远程岗位。只保留这个可稳定筛选的地点结构化字段。",
    )

    employment_type: Mapped[EmploymentType] = mapped_column(
        enum_column(EmploymentType, name="employment_type", length=30),
        nullable=False,
        default=EmploymentType.UNKNOWN,
        server_default=EmploymentType.UNKNOWN.value,
        comment="雇佣类型，例如 full_time、part_time、contract、internship。",
    )

    workplace_type: Mapped[WorkplaceType] = mapped_column(
        enum_column(WorkplaceType, name="workplace_type", length=30),
        nullable=False,
        default=WorkplaceType.UNKNOWN,
        server_default=WorkplaceType.UNKNOWN.value,
        comment="办公方式，例如 onsite、hybrid、remote。",
    )

    experience_level: Mapped[ExperienceLevel] = mapped_column(
        enum_column(ExperienceLevel, name="experience_level", length=30),
        nullable=False,
        default=ExperienceLevel.UNKNOWN,
        server_default=ExperienceLevel.UNKNOWN.value,
        comment="经验等级。",
    )

    experience_min_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="最低经验年限，无法解析则为空。",
    )

    experience_max_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="最高经验年限，无法解析则为空。",
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
        comment="原始薪资文本，例如 10-15K、150-200/天、100-150K/year。",
    )

    salary_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="解析后的最低薪资数值。周期语义保留在 salary_text，不单独结构化。",
    )

    salary_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="解析后的最高薪资数值。周期语义保留在 salary_text，不单独结构化。",
    )

    salary_currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="CNY",
        server_default="CNY",
        comment="薪资币种，默认 CNY。",
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="来源平台发布时间，无法解析则为空。",
    )

    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="系统第一次发现该岗位的时间。",
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="系统最近一次看到该岗位的时间。",
    )

    status: Mapped[JobPostStatus] = mapped_column(
        enum_column(JobPostStatus, name="job_post_status", length=20),
        nullable=False,
        default=JobPostStatus.OPEN,
        server_default=JobPostStatus.OPEN.value,
        comment="规范化岗位状态。",
    )

    source: Mapped[JobSource] = relationship(
        back_populates="job_posts",
    )

    raw_record: Mapped[RawJobRecord | None] = relationship(
        back_populates="job_posts",
    )

    detail: Mapped[JobPostDetail | None] = relationship(
        back_populates="job_post",
        cascade="all, delete-orphan",
        uselist=False,
    )


class JobPostDetail(TimestampMixin, Base):
    """岗位冷数据/详情表。

    保存正文、链接，以及签证/搬迁等海外冷字段。
    MVP 不再为签证单独建表，避免过度拆分。
    """

    __tablename__ = "job_post_details"
    __table_args__ = {
        "comment": "岗位详情冷数据表，保存正文、来源 URL、公司 URL、签证/搬迁等低频字段。",
    }

    job_post_id: Mapped[int] = mapped_column(
        ForeignKey("job_posts.id", ondelete="CASCADE"),
        primary_key=True,
        comment="关联 job_posts.id，同时作为详情表主键。",
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="来源岗位详情 URL。external_job_id 不放这里，放 raw_job_records。",
    )

    company_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="来源平台上的公司 URL，可为空。",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="岗位正文。MVP 合并职责、要求、详情等文本，不单独拆 requirements。",
    )

    has_visa_sponsorship: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="是否明确提供签证支持。冷字段，不参与高频查询。",
    )

    has_relocation_support: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="是否明确提供搬迁支持。冷字段，不参与高频查询。",
    )

    work_authorization_note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="工作许可、签证、搬迁相关的原始说明或清洗后的备注。",
    )

    job_post: Mapped[JobPost] = relationship(
        back_populates="detail",
    )
