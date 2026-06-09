"""add raw job content dedup

Revision ID: e7b8c9d0a1f2
Revises: 9c4d5e6f7a8b
Create Date: 2026-06-09 10:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b8c9d0a1f2"
down_revision: str | Sequence[str] | None = "9c4d5e6f7a8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "raw_job_records",
        sa.Column(
            "seen_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="同一来源 raw 内容被重复看到的次数。",
        ),
    )
    op.create_unique_constraint(
        "uq_raw_job_records_source_hash",
        "raw_job_records",
        ["source_id", "raw_content_hash"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "uq_raw_job_records_source_hash",
        "raw_job_records",
        type_="unique",
    )
    op.drop_column("raw_job_records", "seen_count")
