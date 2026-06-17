from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class UserOwnedMixin:
    """用户私有数据 Mixin。

    主要用于收藏、目标岗位、用户技能画像等用户私有关系表。
    公共字典表、公共内容表、系统表不应该继承该 Mixin。
    """

    __abstract__ = True

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 ID。所有用户私有数据查询都必须带该字段做隔离。",
    )


class SortOrderMixin:
    """用户自定义排序 Mixin。

    dadibadi 中很多表使用 sort 字段表达展示顺序。
    JobPilot 保留这个设计思想，但命名为 sort_order，
    使字段含义更明确，也避免和 SQL 或 Python 里的排序语义混淆。
    """

    __abstract__ = True

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=99,
        server_default="99",
        comment="用户自定义展示排序。数值越小越靠前，默认 99。",
    )


class ArchiveTimestampMixin:
    """归档生命周期 Mixin。

    JobPilot 不直接照搬 dadibadi 的 deleted_flag 整数字段。
    对多数业务记录来说，deleted_at / archived_at / removed_at
    比单纯的 0/1 标记更能表达业务含义和审计信息。
    """

    __abstract__ = True

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="归档时间。当前有效记录为空。",
    )

    def mark_archived(self) -> None:
        """在 flush 之前为内存中的领域对象设置归档时间。"""

        self.archived_at = datetime.now(UTC)
