"""remove producer type field

Revision ID: a0f3799efc1c
Revises: 2aed7153a399
Create Date: 2026-06-05 23:00:38.286036

This revision is intentionally left as a no-op after the job-post schema was squashed
for the MVP rebuild workflow.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a0f3799efc1c"
down_revision: str | Sequence[str] | None = "2aed7153a399"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
