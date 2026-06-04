from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_pilot.db.base import Base, SoftDeleteMixin, TimestampMixin
from job_pilot.modules.users.enums import UserStatus

if TYPE_CHECKING:
    from job_pilot.modules.auth.models import AuthIdentity


class User(TimestampMixin, SoftDeleteMixin, Base):
    """
    平台用户主体。

    设计原则：
    - User 不等于登录账号。
    - User 不直接保存 email / phone / password_hash。
    - email、phone、github_id 等都属于 auth identity。
    - 昵称、头像、简介等属于 user profile。
    """

    __tablename__ = "users"
    __table_args__ = {
        "comment": "平台用户主体表，只保存用户状态、权限标记和生命周期信息。",
    }

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="用户主键 ID。",
    )

    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
        index=True,
        comment="用户账号状态：active 可用，disabled 禁用，deleted 逻辑删除。",
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="是否为平台超级管理员，用于后台管理和越权保护场景。",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="用户最近一次成功登录时间，用于安全审计和活跃度统计。",
    )

    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    identities: Mapped[list[AuthIdentity]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and self.deleted_at is None


class UserProfile(TimestampMixin, Base):
    """
    用户资料表。

    设计原则：
    - 资料信息和认证信息分离。
    - username 是公开用户名 / handle，不等于登录账号。
    - display_name 是展示昵称，可以重复。
    """

    __tablename__ = "user_profiles"
    __table_args__ = {
        "comment": "用户公开资料表，与登录身份和密码凭证分离。",
    }

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="关联 users.id，同时作为用户资料表主键。",
    )

    username: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
        comment="公开用户名或 handle，可为空但填写后必须全局唯一。",
    )

    display_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        comment="页面展示昵称，可以重复，不用于登录认证。",
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="用户头像 URL。",
    )

    bio: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        comment="用户个人简介，控制长度以便直接用于列表和个人页展示。",
    )

    user: Mapped[User] = relationship(
        back_populates="profile",
    )
