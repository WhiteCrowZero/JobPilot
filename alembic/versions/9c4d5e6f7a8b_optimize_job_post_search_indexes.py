"""optimize job post search indexes

Revision ID: 9c4d5e6f7a8b
Revises: 8ea16b985736
Create Date: 2026-06-07 17:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c4d5e6f7a8b"
down_revision: str | Sequence[str] | None = "8ea16b985736"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.drop_index("ix_job_posts_open_published_at", table_name="job_posts")
    op.drop_index("ix_job_posts_open_created_at", table_name="job_posts")

    op.create_index(
        "ix_job_posts_open_published_at_id",
        "job_posts",
        [sa.text("published_at DESC NULLS LAST"), sa.text("id DESC")],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_job_posts_open_published_at_asc_id",
        "job_posts",
        [sa.text("published_at ASC NULLS LAST"), sa.text("id ASC")],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_job_posts_open_created_at_id",
        "job_posts",
        [sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_job_posts_open_salary_max_id",
        "job_posts",
        [sa.text("salary_max DESC NULLS LAST"), sa.text("id DESC")],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_job_posts_open_salary_min_id",
        "job_posts",
        [sa.text("salary_min ASC NULLS LAST"), sa.text("id ASC")],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_job_posts_open_salary_min_id",
        table_name="job_posts",
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.drop_index(
        "ix_job_posts_open_salary_max_id",
        table_name="job_posts",
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.drop_index(
        "ix_job_posts_open_created_at_id",
        table_name="job_posts",
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.drop_index(
        "ix_job_posts_open_published_at_id",
        table_name="job_posts",
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.drop_index(
        "ix_job_posts_open_published_at_asc_id",
        table_name="job_posts",
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )

    op.create_index(
        "ix_job_posts_open_published_at",
        "job_posts",
        ["published_at"],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_job_posts_open_created_at",
        "job_posts",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND deleted_at IS NULL"),
    )
