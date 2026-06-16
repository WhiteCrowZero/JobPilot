from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, TimestampMixin
from job_pilot.modules.knowledge.enums import (
    ContentSourceType,
    KnowledgePointLevel,
    KnowledgePointStatus,
)

if TYPE_CHECKING:
    from job_pilot.modules.job_skills.models import Skill
    from job_pilot.modules.questions.models import QuestionSkill
    from job_pilot.modules.users.models import User


class KnowledgePoint(TimestampMixin, Base):
    """轻量知识点树。

    知识点不是文章库，只作为技能下的分类节点，用于题目归类、学习任务聚合和后续路线组织。
    """

    __tablename__ = "knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "skill_id", "parent_id", "title", name="uq_knowledge_points_sibling_title"
        ),
        CheckConstraint("depth >= 0", name="ck_knowledge_points_depth_non_negative"),
        CheckConstraint("sort_order >= 0", name="ck_knowledge_points_sort_order_non_negative"),
        Index(
            "ix_knowledge_points_skill_parent_sort",
            "skill_id",
            "parent_id",
            "sort_order",
            "id",
            postgresql_where=text("status = 'active'"),
        ),
        {"comment": "轻量知识点树，用于按技能组织题目和学习任务。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="知识点主键 ID。",
    )

    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
        comment="所属标准技能 ID，关联 skills.id。",
    )

    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
        comment="父知识点 ID，自关联形成邻接表树结构。",
    )

    title: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        comment="知识点标题，同一父节点下不重复。",
    )

    summary: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="知识点简短说明。MVP 不保存大段资料正文。",
    )

    level: Mapped[KnowledgePointLevel] = mapped_column(
        enum_column(KnowledgePointLevel, name="knowledge_point_level", length=30),
        nullable=False,
        default=KnowledgePointLevel.BASIC,
        server_default=KnowledgePointLevel.BASIC.value,
        comment="知识点难度层级。",
    )

    depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="知识点树深度，根节点为 0。由 service 维护。",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=99,
        server_default="99",
        comment="同一父节点下的展示顺序。",
    )

    status: Mapped[KnowledgePointStatus] = mapped_column(
        enum_column(KnowledgePointStatus, name="knowledge_point_status", length=20),
        nullable=False,
        default=KnowledgePointStatus.ACTIVE,
        server_default=KnowledgePointStatus.ACTIVE.value,
        comment="知识点状态。",
    )

    source_type: Mapped[ContentSourceType] = mapped_column(
        enum_column(ContentSourceType, name="content_source_type", length=30),
        nullable=False,
        default=ContentSourceType.OFFICIAL,
        server_default=ContentSourceType.OFFICIAL.value,
        comment="内容来源：ai、official、user_supplement。",
    )

    source_note: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        comment="来源补充说明，不保存外部资料正文。",
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="用户补充内容的创建者 ID，官方或 AI 内容可为空。",
    )

    skill: Mapped[Skill] = relationship(
        back_populates="knowledge_points",
    )

    parent: Mapped[KnowledgePoint | None] = relationship(
        remote_side="KnowledgePoint.id",
        back_populates="children",
    )

    children: Mapped[list[KnowledgePoint]] = relationship(
        back_populates="parent",
    )

    created_by_user: Mapped[User | None] = relationship(
        foreign_keys=[created_by_user_id],
    )

    question_links: Mapped[list[QuestionSkill]] = relationship(
        back_populates="knowledge_point",
    )
