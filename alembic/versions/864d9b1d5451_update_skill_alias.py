"""update skill alias

Revision ID: 864d9b1d5451
Revises: d757db30fc0e
Create Date: 2026-06-10 18:27:45.951568

"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "864d9b1d5451"
down_revision: str | Sequence[str] | None = "d757db30fc0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
