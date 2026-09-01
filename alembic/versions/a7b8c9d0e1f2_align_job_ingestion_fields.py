"""align job ingestion fields

Revision ID: a7b8c9d0e1f2
Revises: f2c3d4e5a6b7
Create Date: 2026-09-01 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f2c3d4e5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """将数据库结构同步到已确认的岗位与 raw 岗位字段。"""

    op.alter_column(
        "job_sources",
        "platform",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        existing_comment="来源平台标识，例如 alibaba、tencent、jaabz；同平台可有多个来源实例。",
        comment="来源平台标识，例如 alibaba、tencent。",
    )
    op.alter_column(
        "job_sources",
        "name",
        existing_type=sa.String(length=100),
        existing_nullable=False,
        existing_comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘、Jaabz。",
        comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘。",
    )
    op.alter_column(
        "job_posts",
        "fingerprint",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        existing_comment="规范化岗位去重指纹。数据库唯一约束兜底防重。",
        comment="规范化岗位去重指纹。",
    )
    op.alter_column(
        "job_posts",
        "title",
        existing_type=sa.String(length=300),
        existing_nullable=False,
        existing_comment="岗位标题，用于列表展示。MVP 使用 ILIKE，后续可接 ES/embedding。",
        comment="岗位标题，用于列表展示。",
    )
    op.alter_column(
        "job_posts",
        "locations",
        existing_type=sa.String(length=500),
        existing_nullable=True,
        existing_comment="岗位地点文本，多个地点用 / 拼接。MVP 不拆国家、城市、区域表。",
        comment="岗位地点文本，多个地点用 / 拼接。",
    )
    op.alter_column(
        "job_posts",
        "salary_text",
        existing_type=sa.String(length=120),
        existing_nullable=True,
        existing_comment="原始薪资文本，例如 10-15K、150-200/天、100-150K/year。",
        comment="原始薪资文本，例如 10-15K、150-200/天。",
    )
    op.alter_column(
        "raw_job_records",
        "producer",
        new_column_name="producer_name",
        existing_type=sa.String(length=100),
        existing_nullable=True,
    )
    op.drop_column("raw_job_records", "skill_content_hash")
    op.drop_column("raw_job_records", "first_seen_at")
    op.drop_column("raw_job_records", "last_seen_at")
    op.drop_column("raw_job_records", "seen_count")

    op.add_column(
        "job_posts",
        sa.Column(
            "experience_text",
            sa.String(length=120),
            nullable=True,
            comment="来源岗位的经验要求文本，例如 3年以上、不限、在校生。",
        ),
    )
    op.add_column(
        "job_posts",
        sa.Column(
            "source_url",
            sa.String(length=1000),
            nullable=True,
            comment="来源岗位详情 URL。",
        ),
    )
    op.add_column(
        "job_posts",
        sa.Column("description", sa.Text(), nullable=True, comment="岗位正文。"),
    )
    op.execute(
        sa.text(
            """
            UPDATE job_posts AS job
            SET source_url = detail.source_url,
                description = detail.description
            FROM job_post_details AS detail
            WHERE detail.job_post_id = job.id
            """
        )
    )
    op.drop_table("job_post_details")

    for column_name in (
        "company_name",
        "is_remote",
        "employment_type",
        "workplace_type",
        "experience_level",
        "experience_min_years",
        "experience_max_years",
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_period",
        "first_seen_at",
        "last_seen_at",
        "skill_content_hash",
    ):
        op.drop_column("job_posts", column_name)


def downgrade() -> None:
    """恢复旧岗位字段，并保留可回填的详情文本。"""

    op.add_column(
        "job_posts",
        sa.Column("company_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "job_posts",
        sa.Column("is_remote", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "job_posts",
        sa.Column(
            "employment_type",
            sa.Enum(
                "full_time",
                "part_time",
                "contract",
                "internship",
                "temporary",
                "freelance",
                "unknown",
                name="employment_type",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "job_posts",
        sa.Column(
            "workplace_type",
            sa.Enum(
                "onsite",
                "hybrid",
                "remote",
                "unknown",
                name="workplace_type",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "job_posts",
        sa.Column(
            "experience_level",
            sa.Enum(
                "intern",
                "entry",
                "junior",
                "mid",
                "senior",
                "lead",
                "director",
                "not_applicable",
                "unknown",
                name="experience_level",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column("job_posts", sa.Column("experience_min_years", sa.Integer(), nullable=True))
    op.add_column("job_posts", sa.Column("experience_max_years", sa.Integer(), nullable=True))
    op.add_column("job_posts", sa.Column("salary_min", sa.Integer(), nullable=True))
    op.add_column("job_posts", sa.Column("salary_max", sa.Integer(), nullable=True))
    op.add_column(
        "job_posts",
        sa.Column(
            "salary_currency",
            sa.String(length=10),
            server_default="CNY",
            nullable=False,
        ),
    )
    op.add_column(
        "job_posts",
        sa.Column(
            "salary_period",
            sa.Enum(
                "hour",
                "day",
                "month",
                "year",
                "unknown",
                name="salary_period",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "job_posts",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "job_posts",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "job_posts",
        sa.Column("skill_content_hash", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "job_post_details",
        sa.Column("job_post_id", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("company_url", sa.String(length=1000), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "has_visa_sponsorship",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "has_relocation_support",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("work_authorization_note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_post_id"], ["job_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_post_id"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO job_post_details (job_post_id, source_url, description)
            SELECT id, source_url, description
            FROM job_posts
            WHERE source_url IS NOT NULL OR description IS NOT NULL
            """
        )
    )
    op.drop_column("job_posts", "description")
    op.drop_column("job_posts", "source_url")
    op.drop_column("job_posts", "experience_text")

    op.add_column(
        "raw_job_records",
        sa.Column("skill_content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "raw_job_records",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "raw_job_records",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "raw_job_records",
        sa.Column("seen_count", sa.Integer(), server_default="1", nullable=False),
    )
    op.alter_column(
        "raw_job_records",
        "producer_name",
        new_column_name="producer",
        existing_type=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "job_posts",
        "salary_text",
        existing_type=sa.String(length=120),
        existing_nullable=True,
        existing_comment="原始薪资文本，例如 10-15K、150-200/天。",
        comment="原始薪资文本，例如 10-15K、150-200/天、100-150K/year。",
    )
    op.alter_column(
        "job_posts",
        "locations",
        existing_type=sa.String(length=500),
        existing_nullable=True,
        existing_comment="岗位地点文本，多个地点用 / 拼接。",
        comment="岗位地点文本，多个地点用 / 拼接。MVP 不拆国家、城市、区域表。",
    )
    op.alter_column(
        "job_posts",
        "title",
        existing_type=sa.String(length=300),
        existing_nullable=False,
        existing_comment="岗位标题，用于列表展示。",
        comment="岗位标题，用于列表展示。MVP 使用 ILIKE，后续可接 ES/embedding。",
    )
    op.alter_column(
        "job_posts",
        "fingerprint",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        existing_comment="规范化岗位去重指纹。",
        comment="规范化岗位去重指纹。数据库唯一约束兜底防重。",
    )
    op.alter_column(
        "job_sources",
        "name",
        existing_type=sa.String(length=100),
        existing_nullable=False,
        existing_comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘。",
        comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘、Jaabz。",
    )
    op.alter_column(
        "job_sources",
        "platform",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        existing_comment="来源平台标识，例如 alibaba、tencent。",
        comment="来源平台标识，例如 alibaba、tencent、jaabz；同平台可有多个来源实例。",
    )
