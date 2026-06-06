"""refine job source identity

Revision ID: d4c9b7e6a2f1
Revises: b65af475e65b
Create Date: 2026-06-06 21:20:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4c9b7e6a2f1"
down_revision: str | Sequence[str] | None = "b65af475e65b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        UPDATE job_sources
        SET
            name = CASE platform
                WHEN 'alibaba' THEN '阿里巴巴社招'
                WHEN 'tencent' THEN '腾讯招聘'
                WHEN 'jaabz' THEN 'Jaabz'
                WHEN 'sample' THEN '示例数据'
                ELSE name
            END,
            base_url = CASE platform
                WHEN 'alibaba' THEN 'https://talent.taotian.com/off-campus'
                WHEN 'tencent' THEN 'https://careers.tencent.com'
                WHEN 'jaabz' THEN 'https://jaabz.com/jobs'
                WHEN 'sample' THEN 'https://example.com/jobpilot/sample'
                ELSE 'https://example.com/jobpilot/source-' || id::text
            END
        WHERE base_url IS NULL OR trim(base_url) = ''
        """
    )
    op.alter_column(
        "job_sources",
        "platform",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        comment="来源平台标识，例如 alibaba、tencent、jaabz；同平台可有多个来源实例。",
        existing_comment="来源平台唯一标识，数据库层不用 enum；代码层通过 adapter registry 适配。",
    )
    op.alter_column(
        "job_sources",
        "name",
        existing_type=sa.String(length=100),
        existing_nullable=False,
        comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘、Jaabz。",
        existing_comment="来源展示名称，例如 阿里巴巴、腾讯、Jaabz。",
    )
    op.alter_column(
        "job_sources",
        "base_url",
        existing_type=sa.String(length=500),
        nullable=False,
        comment="来源实例基础 URL，例如社招入口、校招入口或第三方职位列表页。",
        existing_comment="来源平台基础 URL，可为空。",
    )
    op.execute("ALTER TABLE job_sources DROP CONSTRAINT IF EXISTS uq_job_sources_platform")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_job_sources_platform_base_url'
            ) THEN
                ALTER TABLE job_sources
                    ADD CONSTRAINT uq_job_sources_platform_base_url
                    UNIQUE (platform, base_url);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "ALTER TABLE job_sources DROP CONSTRAINT IF EXISTS uq_job_sources_platform_base_url"
    )
    op.alter_column(
        "job_sources",
        "base_url",
        existing_type=sa.String(length=500),
        nullable=True,
        comment="来源平台基础 URL，可为空。",
        existing_comment="来源实例基础 URL，例如社招入口、校招入口或第三方职位列表页。",
    )
    op.alter_column(
        "job_sources",
        "name",
        existing_type=sa.String(length=100),
        existing_nullable=False,
        comment="来源展示名称，例如 阿里巴巴、腾讯、Jaabz。",
        existing_comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘、Jaabz。",
    )
    op.alter_column(
        "job_sources",
        "platform",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        comment="来源平台唯一标识，数据库层不用 enum；代码层通过 adapter registry 适配。",
        existing_comment="来源平台标识，例如 alibaba、tencent、jaabz；同平台可有多个来源实例。",
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_job_sources_platform'
            ) THEN
                ALTER TABLE job_sources
                    ADD CONSTRAINT uq_job_sources_platform
                    UNIQUE (platform);
            END IF;
        END
        $$;
        """
    )
