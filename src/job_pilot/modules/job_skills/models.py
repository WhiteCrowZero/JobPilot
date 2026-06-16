from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_pilot.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from job_pilot.modules.job_posts.models import JobPost
    from job_pilot.modules.knowledge.models import KnowledgePoint
    from job_pilot.modules.questions.models import QuestionSkill
    from job_pilot.modules.study_tasks.models import StudyTask
    from job_pilot.modules.user_skills.models import UserSkill


class Skill(TimestampMixin, Base):
    """标准技能字典表。"""

    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("name", name="uq_skills_name"),
        {"comment": "标准技能字典表，被岗位、用户技能、八股题等模块复用。"},
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="标准技能主键 ID。",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="标准技能展示名称，例如 Python、FastAPI、PostgreSQL。",
    )

    aliases: Mapped[list[SkillAlias]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
    )

    job_post_links: Mapped[list[JobPostSkill]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
    )

    user_skill_profiles: Mapped[list[UserSkill]] = relationship(
        back_populates="skill",
    )

    knowledge_points: Mapped[list[KnowledgePoint]] = relationship(
        back_populates="skill",
    )

    question_links: Mapped[list[QuestionSkill]] = relationship(
        back_populates="skill",
    )

    study_tasks: Mapped[list[StudyTask]] = relationship(
        back_populates="skill",
    )


class SkillAlias(TimestampMixin, Base):
    """技能别名表。"""

    __tablename__ = "skill_aliases"
    __table_args__ = (
        UniqueConstraint("alias", name="uq_skill_aliases_alias"),
        Index("ix_skill_aliases_skill_id", "skill_id"),
        {"comment": "技能别名表，负责把来源 raw skill 归一到标准 skills。"},
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="技能别名主键 ID。",
    )

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联标准技能 ID。",
    )

    alias: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="别名归一化结果。一个 alias 只允许指向一个标准技能。",
    )

    skill: Mapped[Skill] = relationship(back_populates="aliases")


class JobPostSkill(TimestampMixin, Base):
    """岗位与标准技能的关系表。"""

    __tablename__ = "job_post_skills"
    __table_args__ = (
        UniqueConstraint("job_post_id", "skill_id", name="uq_job_post_skills_job_skill"),
        Index("ix_job_post_skills_skill_job", "skill_id", "job_post_id"),
        {"comment": "岗位技能关系表，只记录岗位与清洗后标准技能的事实关系。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="岗位技能关系主键 ID。",
    )

    job_post_id: Mapped[int] = mapped_column(
        ForeignKey("job_posts.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 job_posts.id。",
    )

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
        comment="关联标准 skills.id。",
    )

    job_post: Mapped[JobPost] = relationship(back_populates="skill_links")

    skill: Mapped[Skill] = relationship(back_populates="job_post_links")
