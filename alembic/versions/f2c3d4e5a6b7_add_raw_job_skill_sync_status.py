"""add raw job skill sync status

Revision ID: f2c3d4e5a6b7
Revises: bcfbbc9e22dd
Create Date: 2026-08-11 23:20:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2c3d4e5a6b7"
down_revision: str | Sequence[str] | None = "bcfbbc9e22dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加可独立诊断的岗位技能同步状态。"""

    op.add_column(
        "raw_job_records",
        sa.Column(
            "skill_sync_status",
            sa.Enum(
                "not_started",
                "pending",
                "succeeded",
                "skipped",
                "failed",
                name="raw_job_skill_sync_status",
                native_enum=False,
                length=30,
                create_constraint=True,
            ),
            server_default="not_started",
            nullable=False,
            comment="岗位技能同步状态，与 raw 规范化状态分开记录。",
        ),
    )
    op.add_column(
        "raw_job_records",
        sa.Column(
            "skill_sync_error_message",
            sa.Text(),
            nullable=True,
            comment="最近一次失败原因。",
        ),
    )
    op.add_column(
        "raw_job_records",
        sa.Column(
            "skill_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="技能同步成功或确认跳过时间。",
        ),
    )


def downgrade() -> None:
    """移除岗位技能同步状态。"""

    op.drop_column("raw_job_records", "skill_synced_at")
    op.drop_column("raw_job_records", "skill_sync_error_message")
    op.drop_column("raw_job_records", "skill_sync_status")
