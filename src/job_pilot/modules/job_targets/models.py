from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, TimestampMixin, UserOwnedMixin
from job_pilot.modules.job_targets.enums import JobTargetStatus

if TYPE_CHECKING:
    from job_pilot.modules.job_collections.models import JobCollection
    from job_pilot.modules.job_posts.models import JobPost
    from job_pilot.modules.users.models import User


class JobTarget(UserOwnedMixin, TimestampMixin, Base):
    """用户目标岗位表。

    目标岗位表示用户正在围绕该岗位做求职准备，不表示投递状态。
    允许一个用户有多个目标岗位，但同一时刻最多只有一个 active/paused 主目标。
    """

    __tablename__ = "job_targets"
    __table_args__ = (
        UniqueConstraint("user_id", "job_post_id", name="uq_job_targets_user_job"),
        CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="ck_job_targets_priority_range",
        ),
        CheckConstraint(
            "status IN ('active', 'paused') OR is_primary = false",
            name="ck_job_targets_primary_current_status",
        ),
        CheckConstraint(
            "("
            "status IN ('active', 'paused') "
            "AND completed_at IS NULL "
            "AND archived_at IS NULL"
            ") OR ("
            "status = 'completed' "
            "AND completed_at IS NOT NULL "
            "AND archived_at IS NULL"
            ") OR ("
            "status = 'archived' "
            "AND archived_at IS NOT NULL"
            ")",
            name="ck_job_targets_status_timestamps",
        ),
        Index(
            "ix_job_targets_user_active_priority",
            "user_id",
            text("is_primary DESC"),
            text("priority ASC"),
            text("targeted_at DESC"),
            text("id DESC"),
            postgresql_where=text("status IN ('active', 'paused')"),
        ),
        Index(
            "uq_job_targets_user_primary_active",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary = true AND status IN ('active', 'paused')"),
        ),
        {"comment": "用户目标岗位表，记录用户准备目标、优先级、主目标和目标状态。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="目标岗位主键 ID。",
    )

    job_post_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("job_posts.id", ondelete="RESTRICT"),
        nullable=False,
        comment="目标岗位 ID，关联 job_posts.id。岗位主数据不应因用户目标被级联删除。",
    )

    source_collection_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("job_collections.id", ondelete="SET NULL"),
        nullable=True,
        comment="从收藏转为目标时关联的收藏记录 ID，可为空。",
    )

    status: Mapped[JobTargetStatus] = mapped_column(
        enum_column(JobTargetStatus, name="job_target_status", length=20),
        nullable=False,
        default=JobTargetStatus.ACTIVE,
        server_default=JobTargetStatus.ACTIVE.value,
        comment="目标状态：active 准备中，paused 暂停，completed 已完成，archived 已归档。",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
        comment="准备优先级，1 最高，5 最低。",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="是否为当前主目标。一个用户最多只能有一个 active/paused 主目标。",
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="用户对目标岗位的准备备注。",
    )

    target_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="用户希望完成该目标准备的日期。",
    )

    targeted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="最近一次设为目标岗位的时间。",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="目标岗位标记完成的时间。",
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="目标岗位归档的时间。",
    )

    user: Mapped[User] = relationship(
        back_populates="job_targets",
    )

    job_post: Mapped[JobPost] = relationship(
        back_populates="targets",
    )

    source_collection: Mapped[JobCollection | None] = relationship(
        back_populates="target",
    )
