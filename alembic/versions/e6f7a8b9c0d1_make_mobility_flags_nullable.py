"""make mobility flags nullable

Revision ID: e6f7a8b9c0d1
Revises: cd2ea9cdf292
Create Date: 2026-06-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "cd2ea9cdf292"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute(
        """
        UPDATE job_post_details
        SET has_visa_sponsorship = NULL
        WHERE has_visa_sponsorship = false
        """
    )
    op.execute(
        """
        UPDATE job_post_details
        SET has_relocation_support = NULL
        WHERE has_relocation_support = false
        """
    )
    op.alter_column(
        "job_post_details",
        "has_visa_sponsorship",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
        existing_comment="是否明确提供签证支持。冷字段，不参与高频查询。",
        comment="是否明确提供签证支持；空表示来源未提及。冷字段，不参与高频查询。",
    )
    op.alter_column(
        "job_post_details",
        "has_relocation_support",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
        existing_comment="是否明确提供搬迁支持。冷字段，不参与高频查询。",
        comment="是否明确提供搬迁支持；空表示来源未提及。冷字段，不参与高频查询。",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute(
        """
        UPDATE job_post_details
        SET has_visa_sponsorship = false
        WHERE has_visa_sponsorship IS NULL
        """
    )
    op.execute(
        """
        UPDATE job_post_details
        SET has_relocation_support = false
        WHERE has_relocation_support IS NULL
        """
    )
    op.alter_column(
        "job_post_details",
        "has_visa_sponsorship",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
        existing_comment="是否明确提供签证支持；空表示来源未提及。冷字段，不参与高频查询。",
        comment="是否明确提供签证支持。冷字段，不参与高频查询。",
    )
    op.alter_column(
        "job_post_details",
        "has_relocation_support",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
        existing_comment="是否明确提供搬迁支持；空表示来源未提及。冷字段，不参与高频查询。",
        comment="是否明确提供搬迁支持。冷字段，不参与高频查询。",
    )
