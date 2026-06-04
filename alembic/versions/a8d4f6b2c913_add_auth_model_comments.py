"""add auth model comments

Revision ID: a8d4f6b2c913
Revises: f2a9c31b7e10
Create Date: 2026-06-05 00:05:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8d4f6b2c913"
down_revision: str | Sequence[str] | None = "f2a9c31b7e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table_comment(
        "auth_identities",
        "用户登录身份表，保存邮箱、手机号、第三方账号等可登录身份。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "id",
        existing_type=sa.Integer(),
        comment="登录身份主键 ID。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "user_id",
        existing_type=sa.Integer(),
        comment="所属用户 ID，关联 users.id。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "provider",
        existing_type=sa.Enum(
            "email",
            "phone",
            "github",
            "google",
            name="auth_provider",
            native_enum=False,
            create_constraint=True,
            length=30,
        ),
        comment="登录身份提供方，例如 email、phone、github、google。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "provider_subject",
        existing_type=sa.String(length=255),
        comment="提供方内的唯一账号标识，例如标准化邮箱、手机号或 OAuth subject。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "provider_email",
        existing_type=sa.String(length=255),
        comment="提供方返回或用户绑定的邮箱地址。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "provider_phone",
        existing_type=sa.String(length=32),
        comment="提供方返回或用户绑定的手机号。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "provider_username",
        existing_type=sa.String(length=100),
        comment="提供方返回的用户名或昵称快照。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "provider_avatar_url",
        existing_type=sa.String(length=500),
        comment="提供方返回的头像 URL 快照。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "identity_verified_at",
        existing_type=sa.DateTime(timezone=True),
        comment="该登录身份被系统确认有效的时间。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "provider_email_verified_at",
        existing_type=sa.DateTime(timezone=True),
        comment="邮箱被提供方或本系统确认可信的时间。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "provider_phone_verified_at",
        existing_type=sa.DateTime(timezone=True),
        comment="手机号被提供方或本系统确认可信的时间。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "linked_at",
        existing_type=sa.DateTime(timezone=True),
        comment="该登录身份绑定到用户的时间。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_identities",
        "last_login_at",
        existing_type=sa.DateTime(timezone=True),
        comment="该登录身份最近一次成功登录时间。",
        existing_comment=None,
    )

    op.create_table_comment(
        "auth_password_credentials",
        "密码凭证表，只保存需要密码登录的身份对应的密码哈希。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_password_credentials",
        "identity_id",
        existing_type=sa.Integer(),
        comment="关联 auth_identities.id，同时作为密码凭证主键。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_password_credentials",
        "password_hash",
        existing_type=sa.String(length=255),
        comment="密码哈希值，不保存明文密码。",
        existing_comment=None,
    )
    op.alter_column(
        "auth_password_credentials",
        "password_updated_at",
        existing_type=sa.DateTime(timezone=True),
        comment="密码最近一次更新时间，用于密码轮换和安全审计。",
        existing_comment=None,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "auth_password_credentials",
        "password_updated_at",
        existing_type=sa.DateTime(timezone=True),
        comment=None,
        existing_comment="密码最近一次更新时间，用于密码轮换和安全审计。",
    )
    op.alter_column(
        "auth_password_credentials",
        "password_hash",
        existing_type=sa.String(length=255),
        comment=None,
        existing_comment="密码哈希值，不保存明文密码。",
    )
    op.alter_column(
        "auth_password_credentials",
        "identity_id",
        existing_type=sa.Integer(),
        comment=None,
        existing_comment="关联 auth_identities.id，同时作为密码凭证主键。",
    )
    op.drop_table_comment(
        "auth_password_credentials",
        existing_comment="密码凭证表，只保存需要密码登录的身份对应的密码哈希。",
    )

    op.alter_column(
        "auth_identities",
        "last_login_at",
        existing_type=sa.DateTime(timezone=True),
        comment=None,
        existing_comment="该登录身份最近一次成功登录时间。",
    )
    op.alter_column(
        "auth_identities",
        "linked_at",
        existing_type=sa.DateTime(timezone=True),
        comment=None,
        existing_comment="该登录身份绑定到用户的时间。",
    )
    op.alter_column(
        "auth_identities",
        "provider_phone_verified_at",
        existing_type=sa.DateTime(timezone=True),
        comment=None,
        existing_comment="手机号被提供方或本系统确认可信的时间。",
    )
    op.alter_column(
        "auth_identities",
        "provider_email_verified_at",
        existing_type=sa.DateTime(timezone=True),
        comment=None,
        existing_comment="邮箱被提供方或本系统确认可信的时间。",
    )
    op.alter_column(
        "auth_identities",
        "identity_verified_at",
        existing_type=sa.DateTime(timezone=True),
        comment=None,
        existing_comment="该登录身份被系统确认有效的时间。",
    )
    op.alter_column(
        "auth_identities",
        "provider_avatar_url",
        existing_type=sa.String(length=500),
        comment=None,
        existing_comment="提供方返回的头像 URL 快照。",
    )
    op.alter_column(
        "auth_identities",
        "provider_username",
        existing_type=sa.String(length=100),
        comment=None,
        existing_comment="提供方返回的用户名或昵称快照。",
    )
    op.alter_column(
        "auth_identities",
        "provider_phone",
        existing_type=sa.String(length=32),
        comment=None,
        existing_comment="提供方返回或用户绑定的手机号。",
    )
    op.alter_column(
        "auth_identities",
        "provider_email",
        existing_type=sa.String(length=255),
        comment=None,
        existing_comment="提供方返回或用户绑定的邮箱地址。",
    )
    op.alter_column(
        "auth_identities",
        "provider_subject",
        existing_type=sa.String(length=255),
        comment=None,
        existing_comment="提供方内的唯一账号标识，例如标准化邮箱、手机号或 OAuth subject。",
    )
    op.alter_column(
        "auth_identities",
        "provider",
        existing_type=sa.Enum(
            "email",
            "phone",
            "github",
            "google",
            name="auth_provider",
            native_enum=False,
            create_constraint=True,
            length=30,
        ),
        comment=None,
        existing_comment="登录身份提供方，例如 email、phone、github、google。",
    )
    op.alter_column(
        "auth_identities",
        "user_id",
        existing_type=sa.Integer(),
        comment=None,
        existing_comment="所属用户 ID，关联 users.id。",
    )
    op.alter_column(
        "auth_identities",
        "id",
        existing_type=sa.Integer(),
        comment=None,
        existing_comment="登录身份主键 ID。",
    )
    op.drop_table_comment(
        "auth_identities",
        existing_comment="用户登录身份表，保存邮箱、手机号、第三方账号等可登录身份。",
    )
