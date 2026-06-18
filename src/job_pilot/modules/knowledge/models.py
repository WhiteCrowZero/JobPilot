from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, TimestampMixin
from job_pilot.modules.knowledge.enums import (
    KnowledgePointLevel,
    KnowledgePointStatus,
)

if TYPE_CHECKING:
    from job_pilot.modules.job_skills.models import Skill
    from job_pilot.modules.questions.models import QuestionSkill


class KnowledgePoint(TimestampMixin, Base):
    """轻量知识点树。

    知识点不是文章库，只作为技能下的分类节点，用于题目归类、学习任务聚合和后续路线组织。
    """

    __tablename__ = "knowledge_points"
    __table_args__ = (
        Index(
            "uq_knowledge_points_root_title",
            "skill_id",
            "title",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
        ),
        Index(
            "uq_knowledge_points_child_title",
            "skill_id",
            "parent_id",
            "title",
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL"),
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
        comment="知识点简短说明。",
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

    question_links: Mapped[list[QuestionSkill]] = relationship(
        back_populates="knowledge_point",
    )
