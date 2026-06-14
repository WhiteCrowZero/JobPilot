"""add default collection folder

Revision ID: b3e3f2a9c8d1
Revises: 91efd5b091d8
Create Date: 2026-06-14 13:20:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3e3f2a9c8d1"
down_revision: str | Sequence[str] | None = "91efd5b091d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "job_collection_folders",
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否为用户默认收藏夹。默认收藏夹不可归档，每个用户最多一个。",
        ),
    )
    op.create_index(
        "uq_job_collection_folders_user_default",
        "job_collection_folders",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )
    op.execute(
        """
        INSERT INTO job_collection_folders (
            user_id,
            name,
            status,
            is_default,
            sort_order,
            archived_at,
            created_at,
            updated_at
        )
        SELECT
            users.id,
            '默认收藏夹',
            'active',
            true,
            0,
            NULL,
            now(),
            now()
        FROM users
        ON CONFLICT (user_id, name) DO UPDATE SET
            status = 'active',
            is_default = true,
            sort_order = 0,
            archived_at = NULL,
            updated_at = now()
        """
    )
    op.execute(
        """
        UPDATE job_collections AS collection
        SET folder_id = folder.id,
            updated_at = now()
        FROM job_collection_folders AS folder
        WHERE collection.user_id = folder.user_id
          AND folder.is_default = true
          AND collection.folder_id IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute(
        """
        UPDATE job_collections AS collection
        SET folder_id = NULL,
            updated_at = now()
        FROM job_collection_folders AS folder
        WHERE collection.folder_id = folder.id
          AND folder.is_default = true
        """
    )
    op.execute("DELETE FROM job_collection_folders WHERE is_default = true")
    op.drop_index(
        "uq_job_collection_folders_user_default",
        table_name="job_collection_folders",
        postgresql_where=sa.text("is_default = true"),
    )
    op.drop_column("job_collection_folders", "is_default")
