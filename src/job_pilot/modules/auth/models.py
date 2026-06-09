from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, TimestampMixin
from job_pilot.modules.auth.enums import AuthProvider

if TYPE_CHECKING:
    from job_pilot.modules.users.models import User


class AuthIdentity(TimestampMixin, Base):
    """
    登录身份表。

    一条记录表示一个可登录身份，例如：
    - email: 123@qq.com
    - phone: +8613812345678
    - github: github_user_id
    - google: google_sub

    MVP 阶段可以只实现 email/password，
    但表结构已经支持后续第三方登录和多账号绑定。
    """

    __tablename__ = "auth_identities"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_auth_identities_provider_subject",
        ),
        UniqueConstraint(
            "user_id",
            "provider",
            name="uq_auth_identities_user_provider",
        ),
        {
            "comment": "用户登录身份表，保存邮箱、手机号、第三方账号等可登录身份。",
        },
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="登录身份主键 ID。",
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 ID，关联 users.id。",
    )

    provider: Mapped[AuthProvider] = mapped_column(
        enum_column(AuthProvider, "auth_provider", 30),
        nullable=False,
        comment="登录身份提供方，例如 email、phone、github、google。",
    )

    # 通用外部账号唯一标识：
    # email -> normalized_email
    # phone -> normalized_phone
    # google -> sub
    # github -> id
    # wechat -> unionid/openid
    provider_subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="提供方内的唯一账号标识，例如标准化邮箱、手机号或 OAuth subject。",
    )

    provider_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="提供方返回或用户绑定的邮箱地址。",
    )

    provider_phone: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="提供方返回或用户绑定的手机号。",
    )

    provider_username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="提供方返回的用户名或昵称快照。",
    )

    provider_avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="提供方返回的头像 URL 快照。",
    )

    # 这个 identity 本身什么时候被确认有效。
    # email: 点过邮箱验证链接后设置
    # phone: 通过短信验证码后设置
    # github/google: OAuth/OIDC 回调验证成功后设置
    identity_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="该登录身份被系统确认有效的时间。",
    )

    # provider 返回的 email 是否可信，或者本系统是否验证过该 email。
    provider_email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="邮箱被提供方或本系统确认可信的时间。",
    )

    # provider 返回的 phone 是否可信，或者本系统是否验证过该手机号。
    provider_phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="手机号被提供方或本系统确认可信的时间。",
    )

    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="该登录身份绑定到用户的时间。",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="该登录身份最近一次成功登录时间。",
    )

    user: Mapped[User] = relationship(
        back_populates="identities",
    )

    password_credential: Mapped[AuthPasswordCredential | None] = relationship(
        back_populates="identity",
        cascade="all, delete-orphan",
        uselist=False,
    )


class AuthPasswordCredential(TimestampMixin, Base):
    """
    密码凭证表。

    只有 email/password 或 phone/password 这类登录方式需要密码凭证。
    GitHub、Google 等 OAuth 登录身份不需要这张表中的记录。
    """

    __tablename__ = "auth_password_credentials"
    __table_args__ = {
        "comment": "密码凭证表，只保存需要密码登录的身份对应的密码哈希。",
    }

    identity_id: Mapped[int] = mapped_column(
        ForeignKey("auth_identities.id", ondelete="CASCADE"),
        primary_key=True,
        comment="关联 auth_identities.id，同时作为密码凭证主键。",
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码哈希值，不保存明文密码。",
    )

    password_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="密码最近一次更新时间，用于密码轮换和安全审计。",
    )

    identity: Mapped[AuthIdentity] = relationship(
        back_populates="password_credential",
    )
