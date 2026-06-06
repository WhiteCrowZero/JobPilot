"""remove language field

Revision ID: f88d86efb9bb
Revises: 2e545462cf51
Create Date: 2026-06-05 22:16:34.406777

This revision is intentionally left as a no-op after the job-post schema was squashed
for the MVP rebuild workflow.
"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f88d86efb9bb"
down_revision: str | Sequence[str] | None = "2e545462cf51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
