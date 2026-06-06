"""remove normalized_title field

Revision ID: 2e545462cf51
Revises: a0f3799efc1c
Create Date: 2026-06-05 23:28:25.667539

This revision is intentionally left as a no-op after the job-post schema was squashed
for the MVP rebuild workflow.
"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "2e545462cf51"
down_revision: str | Sequence[str] | None = "a0f3799efc1c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
