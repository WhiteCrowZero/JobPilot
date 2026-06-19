from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from job_pilot.core.enums import enum_column
from job_pilot.db.base import (
    ArchiveTimestampMixin,
    Base,
    SortOrderMixin,
    TimestampMixin,
    UserOwnedMixin,
)
from job_pilot.modules.job_collections.enums import JobCollectionFolderStatus, JobCollectionStatus

if TYPE_CHECKING:
    from job_pilot.modules.job_posts.models import JobPost
    from job_pilot.modules.job_targets.models import JobTarget
    from job_pilot.modules.users.models import User


class JobCollectionFolder(
    SortOrderMixin, ArchiveTimestampMixin, UserOwnedMixin, TimestampMixin, Base
):
    """用户岗位收藏夹表。

    收藏夹只负责组织用户自己的收藏关系，不保存岗位快照，也不代表公共岗位集合。
    MVP 只做单层收藏夹；系统会为每个用户维护一个不可归档的默认收藏夹。
    """

    __tablename__ = "job_collection_folders"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_job_collection_folders_user_name"),
        CheckConstraint(
            "(status = 'active' AND archived_at IS NULL) "
            "OR (status = 'archived' AND archived_at IS NOT NULL)",
            name="ck_job_collection_folders_status_archived_at",
        ),
        Index(
            "ix_job_collection_folders_user_active_sort",
            "user_id",
            "sort_order",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_job_collection_folders_user_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        {"comment": "用户岗位收藏夹表，用于单层组织用户收藏岗位。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="收藏夹主键 ID。",
    )

    name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        comment="收藏夹名称。同一用户下不允许重名。",
    )

    status: Mapped[JobCollectionFolderStatus] = mapped_column(
        enum_column(JobCollectionFolderStatus, name="job_collection_folder_status", length=20),
        nullable=False,
        default=JobCollectionFolderStatus.ACTIVE,
        server_default=JobCollectionFolderStatus.ACTIVE.value,
        comment="收藏夹状态：active 当前使用，archived 已归档。",
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="是否为用户默认收藏夹。默认收藏夹不可归档，每个用户最多一个。",
    )

    user: Mapped[User] = relationship(
        back_populates="job_collection_folders",
    )

    collections: Mapped[list[JobCollection]] = relationship(
        back_populates="folder",
    )


class JobCollection(UserOwnedMixin, TimestampMixin, Base):
    """用户岗位收藏表。

    收藏表示用户对岗位感兴趣，是后续设置目标岗位的轻量入口。
    使用 user_id 做强隔离，同一用户对同一岗位只保留一条收藏记录，通过状态实现取消和恢复。
    """

    __tablename__ = "job_collections"
    __table_args__ = (
        UniqueConstraint("user_id", "job_post_id", name="uq_job_collections_user_job"),
        CheckConstraint(
            "(status = 'active' AND removed_at IS NULL) "
            "OR (status = 'removed' AND removed_at IS NOT NULL)",
            name="ck_job_collections_status_removed_at",
        ),
        Index(
            "ix_job_collections_user_folder_active_collected_at",
            "user_id",
            "folder_id",
            text("collected_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_job_collections_user_active_collected_at",
            "user_id",
            text("collected_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'active'"),
        ),
        {"comment": "用户岗位收藏表，记录用户对岗位的兴趣关系和取消状态。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="岗位收藏主键 ID。",
    )

    job_post_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("job_posts.id", ondelete="RESTRICT"),
        nullable=False,
        comment="被收藏岗位 ID，关联 job_posts.id。岗位主数据不应因用户收藏被级联删除。",
    )

    folder_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("job_collection_folders.id", ondelete="SET NULL"),
        nullable=True,
        comment="收藏所属收藏夹 ID。默认情况下指向用户默认收藏夹。",
    )

    status: Mapped[JobCollectionStatus] = mapped_column(
        enum_column(JobCollectionStatus, name="job_collection_status", length=20),
        nullable=False,
        default=JobCollectionStatus.ACTIVE,
        server_default=JobCollectionStatus.ACTIVE.value,
        comment="收藏状态：active 表示当前收藏，removed 表示用户已取消收藏。",
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="用户对该收藏岗位的简短备注。",
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="最近一次收藏或恢复收藏的时间。",
    )

    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近一次取消收藏的时间。当前 active 时为空。",
    )

    user: Mapped[User] = relationship(
        back_populates="job_collections",
    )

    job_post: Mapped[JobPost] = relationship(
        back_populates="collections",
    )

    folder: Mapped[JobCollectionFolder | None] = relationship(
        back_populates="collections",
    )

    target: Mapped[JobTarget | None] = relationship(
        back_populates="source_collection",
        uselist=False,
    )
