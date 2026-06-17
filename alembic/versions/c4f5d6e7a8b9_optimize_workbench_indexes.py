# ruff: noqa: E501
"""optimize workbench indexes

Revision ID: c4f5d6e7a8b9
Revises: b3e3f2a9c8d1
Create Date: 2026-06-14 14:35:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4f5d6e7a8b9"
down_revision: str | Sequence[str] | None = "b3e3f2a9c8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.drop_index(
        op.f("ix_job_collection_folders_user_id"),
        table_name="job_collection_folders",
    )
    op.drop_index(
        "ix_job_collections_job_active",
        table_name="job_collections",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        op.f("ix_job_collections_user_id"),
        table_name="job_collections",
    )

    op.drop_constraint(
        "uq_job_targets_source_collection",
        "job_targets",
        type_="unique",
    )
    op.drop_index(
        "ix_job_targets_user_active_priority",
        table_name="job_targets",
        postgresql_where=sa.text("status IN ('active', 'paused')"),
    )
    op.create_index(
        "ix_job_targets_user_active_priority",
        "job_targets",
        [
            "user_id",
            sa.literal_column("is_primary DESC"),
            sa.literal_column("priority ASC"),
            sa.literal_column("targeted_at DESC"),
            sa.literal_column("id DESC"),
        ],
        unique=False,
        postgresql_where=sa.text("status IN ('active', 'paused')"),
    )
    op.drop_index("ix_job_targets_job_status", table_name="job_targets")
    op.drop_index(op.f("ix_job_targets_user_id"), table_name="job_targets")

    op.drop_index(
        "ix_user_skills_user_active_level",
        table_name="user_skills",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_user_skills_user_active_level",
        "user_skills",
        [
            "user_id",
            sa.literal_column("proficiency_level DESC"),
            sa.literal_column("updated_at DESC"),
        ],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        "ix_user_skills_skill_active",
        table_name="user_skills",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(op.f("ix_user_skills_user_id"), table_name="user_skills")


def downgrade() -> None:
    """Downgrade schema."""

    op.create_index(
        op.f("ix_user_skills_user_id"),
        "user_skills",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_skills_skill_active",
        "user_skills",
        ["skill_id"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        "ix_user_skills_user_active_level",
        table_name="user_skills",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_user_skills_user_active_level",
        "user_skills",
        ["user_id", "proficiency_level", sa.literal_column("updated_at DESC")],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_index(
        op.f("ix_job_targets_user_id"),
        "job_targets",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_job_targets_job_status",
        "job_targets",
        ["job_post_id", "status"],
        unique=False,
    )
    op.drop_index(
        "ix_job_targets_user_active_priority",
        table_name="job_targets",
        postgresql_where=sa.text("status IN ('active', 'paused')"),
    )
    op.create_index(
        "ix_job_targets_user_active_priority",
        "job_targets",
        ["user_id", "priority", sa.literal_column("targeted_at DESC")],
        unique=False,
        postgresql_where=sa.text("status IN ('active', 'paused')"),
    )
    op.create_unique_constraint(
        "uq_job_targets_source_collection",
        "job_targets",
        ["source_collection_id"],
    )

    op.create_index(
        op.f("ix_job_collections_user_id"),
        "job_collections",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_job_collections_job_active",
        "job_collections",
        ["job_post_id"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        op.f("ix_job_collection_folders_user_id"),
        "job_collection_folders",
        ["user_id"],
        unique=False,
    )
