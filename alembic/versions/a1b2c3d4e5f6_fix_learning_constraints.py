"""fix learning constraints

Revision ID: a1b2c3d4e5f6
Revises: 9dccae396c94
Create Date: 2026-06-18 16:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "9dccae396c94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.drop_constraint(
        "uq_knowledge_points_sibling_title",
        "knowledge_points",
        type_="unique",
    )
    op.create_index(
        "uq_knowledge_points_root_title",
        "knowledge_points",
        ["skill_id", "title"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index(
        "uq_knowledge_points_child_title",
        "knowledge_points",
        ["skill_id", "parent_id", "title"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )

    op.drop_constraint(
        "uq_question_skills_question_skill_knowledge",
        "question_skills",
        type_="unique",
    )
    op.create_index(
        "uq_question_skills_question_skill_no_knowledge",
        "question_skills",
        ["question_id", "skill_id"],
        unique=True,
        postgresql_where=sa.text("knowledge_point_id IS NULL"),
    )
    op.create_index(
        "uq_question_skills_question_skill_knowledge",
        "question_skills",
        ["question_id", "skill_id", "knowledge_point_id"],
        unique=True,
        postgresql_where=sa.text("knowledge_point_id IS NOT NULL"),
    )

    op.execute("UPDATE questions SET source_type = 'official' WHERE source_type = 'ai'")
    op.execute("UPDATE question_answers SET source_type = 'official' WHERE source_type = 'ai'")
    op.execute(
        """
        UPDATE questions
        SET question_type = 'interview_open'
        WHERE question_type IN ('short_answer', 'coding')
        """
    )
    op.drop_constraint("question_source_type", "questions", type_="check")
    op.create_check_constraint(
        "question_source_type",
        "questions",
        "source_type IN ('official', 'user_supplement')",
    )
    op.drop_constraint("question_answer_source_type", "question_answers", type_="check")
    op.create_check_constraint(
        "question_answer_source_type",
        "question_answers",
        "source_type IN ('official', 'user_supplement')",
    )
    op.drop_constraint("question_type", "questions", type_="check")
    op.create_check_constraint(
        "question_type",
        "questions",
        "question_type IN ('interview_open', 'single_choice', 'multiple_choice', 'true_false')",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint("question_type", "questions", type_="check")
    op.create_check_constraint(
        "question_type",
        "questions",
        (
            "question_type IN ("
            "'interview_open', 'single_choice', 'multiple_choice', "
            "'true_false', 'short_answer', 'coding'"
            ")"
        ),
    )
    op.drop_constraint("question_answer_source_type", "question_answers", type_="check")
    op.create_check_constraint(
        "question_answer_source_type",
        "question_answers",
        "source_type IN ('ai', 'official', 'user_supplement')",
    )
    op.drop_constraint("question_source_type", "questions", type_="check")
    op.create_check_constraint(
        "question_source_type",
        "questions",
        "source_type IN ('ai', 'official', 'user_supplement')",
    )

    op.drop_index(
        "uq_question_skills_question_skill_knowledge",
        table_name="question_skills",
        postgresql_where=sa.text("knowledge_point_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_question_skills_question_skill_no_knowledge",
        table_name="question_skills",
        postgresql_where=sa.text("knowledge_point_id IS NULL"),
    )
    op.create_unique_constraint(
        "uq_question_skills_question_skill_knowledge",
        "question_skills",
        ["question_id", "skill_id", "knowledge_point_id"],
    )

    op.drop_index(
        "uq_knowledge_points_child_title",
        table_name="knowledge_points",
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_knowledge_points_root_title",
        table_name="knowledge_points",
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_unique_constraint(
        "uq_knowledge_points_sibling_title",
        "knowledge_points",
        ["skill_id", "parent_id", "title"],
    )
