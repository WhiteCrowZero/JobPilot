"""update job post tables

Revision ID: b65af475e65b
Revises: f88d86efb9bb
Create Date: 2026-06-06 20:40:58.339669

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b65af475e65b"
down_revision: str | Sequence[str] | None = "f88d86efb9bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.drop_index(op.f("ix_auth_identities_provider_phone"), table_name="auth_identities")
    op.create_index(
        op.f("ix_auth_identities_provider_phone"),
        "auth_identities",
        ["provider_phone"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(op.f("ix_auth_identities_provider_phone"), table_name="auth_identities")
    op.create_index(
        op.f("ix_auth_identities_provider_phone"),
        "auth_identities",
        ["provider", "provider_phone"],
        unique=False,
    )
