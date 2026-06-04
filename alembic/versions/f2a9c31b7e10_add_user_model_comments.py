"""add user model comments

Revision ID: f2a9c31b7e10
Revises: 096de209d423
Create Date: 2026-06-04 23:45:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a9c31b7e10"
down_revision: str | Sequence[str] | None = "096de209d423"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table_comment(
        "users",
        "平台用户主体表，只保存用户状态、权限标记和生命周期信息。",
        existing_comment=None,
    )
    op.alter_column(
        "users",
        "id",
        existing_type=sa.Integer(),
        comment="用户主键 ID。",
        existing_comment=None,
    )
    op.alter_column(
        "users",
        "status",
        existing_type=sa.Enum(
            "active",
            "disabled",
            "deleted",
            name="user_status",
            native_enum=False,
            create_constraint=True,
            length=20,
        ),
        comment="用户账号状态：active 可用，disabled 禁用，deleted 逻辑删除。",
        existing_comment=None,
    )
    op.alter_column(
        "users",
        "is_superuser",
        existing_type=sa.Boolean(),
        comment="是否为平台超级管理员，用于后台管理和越权保护场景。",
        existing_comment=None,
    )
    op.alter_column(
        "users",
        "last_login_at",
        existing_type=sa.DateTime(timezone=True),
        comment="用户最近一次成功登录时间，用于安全审计和活跃度统计。",
        existing_comment=None,
    )

    op.create_table_comment(
        "user_profiles",
        "用户公开资料表，与登录身份和密码凭证分离。",
        existing_comment=None,
    )
    op.alter_column(
        "user_profiles",
        "user_id",
        existing_type=sa.Integer(),
        comment="关联 users.id，同时作为用户资料表主键。",
        existing_comment=None,
    )
    op.alter_column(
        "user_profiles",
        "username",
        existing_type=sa.String(length=50),
        comment="公开用户名或 handle，可为空但填写后必须全局唯一。",
        existing_comment=None,
    )
    op.alter_column(
        "user_profiles",
        "display_name",
        existing_type=sa.String(length=80),
        comment="页面展示昵称，可以重复，不用于登录认证。",
        existing_comment=None,
    )
    op.alter_column(
        "user_profiles",
        "avatar_url",
        existing_type=sa.String(length=500),
        comment="用户头像 URL。",
        existing_comment=None,
    )
    op.alter_column(
        "user_profiles",
        "bio",
        existing_type=sa.String(length=300),
        comment="用户个人简介，控制长度以便直接用于列表和个人页展示。",
        existing_comment=None,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "user_profiles",
        "bio",
        existing_type=sa.String(length=300),
        comment=None,
        existing_comment="用户个人简介，控制长度以便直接用于列表和个人页展示。",
    )
    op.alter_column(
        "user_profiles",
        "avatar_url",
        existing_type=sa.String(length=500),
        comment=None,
        existing_comment="用户头像 URL。",
    )
    op.alter_column(
        "user_profiles",
        "display_name",
        existing_type=sa.String(length=80),
        comment=None,
        existing_comment="页面展示昵称，可以重复，不用于登录认证。",
    )
    op.alter_column(
        "user_profiles",
        "username",
        existing_type=sa.String(length=50),
        comment=None,
        existing_comment="公开用户名或 handle，可为空但填写后必须全局唯一。",
    )
    op.alter_column(
        "user_profiles",
        "user_id",
        existing_type=sa.Integer(),
        comment=None,
        existing_comment="关联 users.id，同时作为用户资料表主键。",
    )
    op.drop_table_comment(
        "user_profiles",
        existing_comment="用户公开资料表，与登录身份和密码凭证分离。",
    )

    op.alter_column(
        "users",
        "last_login_at",
        existing_type=sa.DateTime(timezone=True),
        comment=None,
        existing_comment="用户最近一次成功登录时间，用于安全审计和活跃度统计。",
    )
    op.alter_column(
        "users",
        "is_superuser",
        existing_type=sa.Boolean(),
        comment=None,
        existing_comment="是否为平台超级管理员，用于后台管理和越权保护场景。",
    )
    op.alter_column(
        "users",
        "status",
        existing_type=sa.Enum(
            "active",
            "disabled",
            "deleted",
            name="user_status",
            native_enum=False,
            create_constraint=True,
            length=20,
        ),
        comment=None,
        existing_comment="用户账号状态：active 可用，disabled 禁用，deleted 逻辑删除。",
    )
    op.alter_column(
        "users",
        "id",
        existing_type=sa.Integer(),
        comment=None,
        existing_comment="用户主键 ID。",
    )
    op.drop_table_comment(
        "users",
        existing_comment="平台用户主体表，只保存用户状态、权限标记和生命周期信息。",
    )
