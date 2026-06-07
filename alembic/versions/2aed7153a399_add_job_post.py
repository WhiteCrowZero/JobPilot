# ruff: noqa: E501
"""add job post

Revision ID: 2aed7153a399
Revises: c4f7a1b9e2d0
Create Date: 2026-06-05 19:59:59.132830

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2aed7153a399"
down_revision: str | Sequence[str] | None = "c4f7a1b9e2d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "job_sources",
        sa.Column(
            "id", sa.Integer(), autoincrement=True, nullable=False, comment="岗位来源主键 ID。"
        ),
        sa.Column(
            "platform",
            sa.String(length=50),
            nullable=False,
            comment="来源平台标识，例如 alibaba、tencent、jaabz；同平台可有多个来源实例。",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="来源展示名称，例如 阿里社招、阿里校招、腾讯招聘、Jaabz。",
        ),
        sa.Column(
            "base_url",
            sa.String(length=500),
            nullable=False,
            comment="来源实例基础 URL，例如社招入口、校招入口或第三方职位列表页。",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="该来源是否启用。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "base_url", name="uq_job_sources_platform_base_url"),
        comment="岗位来源表，同一平台可按不同 base_url 拆分具体来源。",
    )

    op.create_table(
        "raw_job_records",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="原始岗位记录主键 ID。",
        ),
        sa.Column(
            "source_id", sa.Integer(), nullable=False, comment="来源 ID，关联 job_sources.id。"
        ),
        sa.Column(
            "message_id",
            sa.String(length=64),
            nullable=True,
            comment="消息唯一 ID。RabbitMQ 模式下用于幂等；文件导入可为空。",
        ),
        sa.Column(
            "trace_id",
            sa.String(length=64),
            nullable=True,
            comment="链路追踪 ID，用于串联 crawler、MQ、ingestion worker 日志。",
        ),
        sa.Column(
            "producer",
            sa.String(length=100),
            nullable=True,
            comment="生产者名称，例如 alibaba-crawler、excel-importer。",
        ),
        sa.Column(
            "external_job_id",
            sa.String(length=120),
            nullable=True,
            comment="来源平台自己的岗位 ID。只放 raw 表，不放 job_posts 主表。",
        ),
        sa.Column(
            "source_url",
            sa.String(length=1000),
            nullable=True,
            comment="来源岗位详情 URL。规范化详情表可冗余一份用于展示。",
        ),
        sa.Column(
            "raw_content_hash",
            sa.String(length=64),
            nullable=False,
            comment="raw_payload 规范化序列化后的内容 hash，用于幂等和变化检测。",
        ),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="来源原始字段，PostgreSQL JSONB。",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "received",
                "normalized",
                "failed",
                "skipped",
                name="raw_job_record_status",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="received",
            nullable=False,
            comment="原始记录处理状态。",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="adapter/normalizer 失败时记录错误原因。",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="爬虫采集到该原始记录的时间，文件导入可为空。",
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="后端收到该原始记录的时间。",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="后端完成规范化处理的时间。",
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="系统第一次看到该来源记录的时间。",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="系统最近一次看到该来源记录的时间。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_raw_job_records_message_id"),
        comment="原始岗位记录表，保存爬虫或文件导入推来的 raw payload。",
    )
    op.create_index(
        "ix_raw_job_records_raw_content_hash", "raw_job_records", ["raw_content_hash"], unique=False
    )
    op.create_index(
        "ix_raw_job_records_source_external_job",
        "raw_job_records",
        ["source_id", "external_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_raw_job_records_source_url",
        "raw_job_records",
        ["source_id", "source_url"],
        unique=False,
    )
    op.create_index("ix_raw_job_records_status", "raw_job_records", ["status"], unique=False)

    op.create_table(
        "job_posts",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False, comment="岗位主键 ID。"
        ),
        sa.Column(
            "source_id", sa.Integer(), nullable=False, comment="来源 ID，关联 job_sources.id。"
        ),
        sa.Column(
            "raw_record_id",
            sa.BigInteger(),
            nullable=True,
            comment="最近一次生成或更新该规范化岗位的原始记录 ID。",
        ),
        sa.Column(
            "fingerprint",
            sa.String(length=64),
            nullable=False,
            comment="规范化岗位去重指纹。数据库唯一约束兜底防重。",
        ),
        sa.Column(
            "title",
            sa.String(length=300),
            nullable=False,
            comment="岗位标题，用于列表展示。MVP 使用 ILIKE，后续可接 ES/embedding。",
        ),
        sa.Column(
            "company_name",
            sa.String(length=200),
            nullable=True,
            comment="公司名称。MVP 不单独拆 companies 表。",
        ),
        sa.Column(
            "locations",
            sa.String(length=500),
            nullable=True,
            comment="岗位地点文本，多个地点用 / 拼接。MVP 不拆国家、城市、区域表。",
        ),
        sa.Column(
            "is_remote",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否远程岗位。只保留这个可稳定筛选的地点结构化字段。",
        ),
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
            comment="雇佣类型，例如 full_time、part_time、contract、internship。",
        ),
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
            comment="办公方式，例如 onsite、hybrid、remote。",
        ),
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
            comment="经验等级。",
        ),
        sa.Column(
            "experience_min_years",
            sa.Integer(),
            nullable=True,
            comment="最低经验年限，无法解析则为空。",
        ),
        sa.Column(
            "experience_max_years",
            sa.Integer(),
            nullable=True,
            comment="最高经验年限，无法解析则为空。",
        ),
        sa.Column(
            "education_level",
            sa.Enum(
                "none",
                "associate",
                "bachelor",
                "master",
                "doctor",
                "unknown",
                name="education_level",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="unknown",
            nullable=False,
            comment="学历等级。",
        ),
        sa.Column(
            "salary_text",
            sa.String(length=120),
            nullable=True,
            comment="原始薪资文本，例如 10-15K、150-200/天、100-150K/year。",
        ),
        sa.Column(
            "salary_min",
            sa.Integer(),
            nullable=True,
            comment="解析后的最低薪资数值。周期语义保留在 salary_text，不单独结构化。",
        ),
        sa.Column(
            "salary_max",
            sa.Integer(),
            nullable=True,
            comment="解析后的最高薪资数值。周期语义保留在 salary_text，不单独结构化。",
        ),
        sa.Column(
            "salary_currency",
            sa.String(length=10),
            server_default="CNY",
            nullable=False,
            comment="薪资币种，默认 CNY。",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="来源平台发布时间，无法解析则为空。",
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="系统第一次发现该岗位的时间。",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="系统最近一次看到该岗位的时间。",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "closed",
                "expired",
                "unknown",
                name="job_post_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="open",
            nullable=False,
            comment="规范化岗位状态。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["raw_record_id"], ["raw_job_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_job_posts_fingerprint"),
        comment="规范化岗位热数据表，用于列表、筛选、排序和状态判断。",
    )
    op.create_index(op.f("ix_job_posts_deleted_at"), "job_posts", ["deleted_at"], unique=False)
    op.create_index("ix_job_posts_is_remote", "job_posts", ["is_remote"], unique=False)
    op.create_index("ix_job_posts_raw_record_id", "job_posts", ["raw_record_id"], unique=False)
    op.create_index("ix_job_posts_source_id", "job_posts", ["source_id"], unique=False)
    op.create_index(
        "ix_job_posts_status_created_at", "job_posts", ["status", "created_at"], unique=False
    )
    op.create_index(
        "ix_job_posts_status_published_at", "job_posts", ["status", "published_at"], unique=False
    )

    op.create_table(
        "job_post_details",
        sa.Column(
            "job_post_id",
            sa.BigInteger(),
            nullable=False,
            comment="关联 job_posts.id，同时作为详情表主键。",
        ),
        sa.Column(
            "source_url",
            sa.String(length=1000),
            nullable=True,
            comment="来源岗位详情 URL。external_job_id 不放这里，放 raw_job_records。",
        ),
        sa.Column(
            "company_url",
            sa.String(length=1000),
            nullable=True,
            comment="来源平台上的公司 URL，可为空。",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="岗位正文。MVP 合并职责、要求、详情等文本，不单独拆 requirements。",
        ),
        sa.Column(
            "has_visa_sponsorship",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否明确提供签证支持。冷字段，不参与高频查询。",
        ),
        sa.Column(
            "has_relocation_support",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否明确提供搬迁支持。冷字段，不参与高频查询。",
        ),
        sa.Column(
            "work_authorization_note",
            sa.String(length=500),
            nullable=True,
            comment="工作许可、签证、搬迁相关的原始说明或清洗后的备注。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_post_id"], ["job_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_post_id"),
        comment="岗位详情冷数据表，保存正文、来源 URL、公司 URL、签证/搬迁等低频字段。",
    )

    op.drop_index(op.f("ix_auth_identities_provider_email"), table_name="auth_identities")
    op.create_index(
        op.f("ix_auth_identities_provider_email"),
        "auth_identities",
        ["provider_email"],
        unique=False,
    )
    op.drop_index(op.f("ix_auth_identities_provider_phone"), table_name="auth_identities")
    op.create_index(
        "ix_auth_identities_provider_phone",
        "auth_identities",
        ["provider", "provider_phone"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_auth_identities_provider_phone", table_name="auth_identities")
    op.create_index(
        op.f("ix_auth_identities_provider_phone"),
        "auth_identities",
        ["provider_phone"],
        unique=False,
    )
    op.drop_index(op.f("ix_auth_identities_provider_email"), table_name="auth_identities")
    op.create_index(
        op.f("ix_auth_identities_provider_email"),
        "auth_identities",
        ["provider", "provider_email"],
        unique=False,
    )
    op.drop_table("job_post_details")
    op.drop_index("ix_job_posts_status_published_at", table_name="job_posts")
    op.drop_index("ix_job_posts_status_created_at", table_name="job_posts")
    op.drop_index("ix_job_posts_source_id", table_name="job_posts")
    op.drop_index("ix_job_posts_raw_record_id", table_name="job_posts")
    op.drop_index("ix_job_posts_is_remote", table_name="job_posts")
    op.drop_index(op.f("ix_job_posts_deleted_at"), table_name="job_posts")
    op.drop_table("job_posts")
    op.drop_index("ix_raw_job_records_status", table_name="raw_job_records")
    op.drop_index("ix_raw_job_records_source_url", table_name="raw_job_records")
    op.drop_index("ix_raw_job_records_source_external_job", table_name="raw_job_records")
    op.drop_index("ix_raw_job_records_raw_content_hash", table_name="raw_job_records")
    op.drop_table("raw_job_records")
    op.drop_table("job_sources")
