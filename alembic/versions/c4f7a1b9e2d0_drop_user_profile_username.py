"""drop user profile username

Revision ID: c4f7a1b9e2d0
Revises: a8d4f6b2c913
Create Date: 2026-06-05 10:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f7a1b9e2d0"
down_revision: str | Sequence[str] | None = "a8d4f6b2c913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_user_profiles_username"), table_name="user_profiles")
    op.drop_column("user_profiles", "username")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "user_profiles",
        sa.Column("username", sa.String(length=50), nullable=True),
    )
    op.create_index(
        op.f("ix_user_profiles_username"),
        "user_profiles",
        ["username"],
        unique=True,
    )
