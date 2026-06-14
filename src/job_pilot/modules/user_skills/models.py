from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, TimestampMixin, UserOwnedMixin
from job_pilot.modules.user_skills.enums import UserSkillSource, UserSkillStatus

if TYPE_CHECKING:
    from job_pilot.modules.job_skills.models import Skill
    from job_pilot.modules.users.models import User


class UserSkill(UserOwnedMixin, TimestampMixin, Base):
    """用户技能画像表。

    记录用户对标准技能的掌握程度。
    技能差距分析中，没有 active 记录表示 missing，等级不足表示 weak，等级达标表示 matched。
    """

    __tablename__ = "user_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uq_user_skills_user_skill"),
        CheckConstraint(
            "proficiency_level BETWEEN 1 AND 5",
            name="ck_user_skills_proficiency_level_range",
        ),
        CheckConstraint(
            "interest_level BETWEEN 1 AND 5",
            name="ck_user_skills_interest_level_range",
        ),
        CheckConstraint(
            "years_of_experience IS NULL OR years_of_experience >= 0",
            name="ck_user_skills_years_of_experience_non_negative",
        ),
        CheckConstraint(
            "(status = 'active' AND archived_at IS NULL) "
            "OR (status = 'archived' AND archived_at IS NOT NULL)",
            name="ck_user_skills_status_archived_at",
        ),
        Index(
            "ix_user_skills_user_active_level",
            "user_id",
            text("proficiency_level DESC"),
            text("updated_at DESC"),
            postgresql_where=text("status = 'active'"),
        ),
        {"comment": "用户技能画像表，记录用户对标准技能的掌握等级和补充信息。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="用户技能画像主键 ID。",
    )

    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
        comment="标准技能 ID，关联 skills.id。",
    )

    status: Mapped[UserSkillStatus] = mapped_column(
        enum_column(UserSkillStatus, name="user_skill_status", length=20),
        nullable=False,
        default=UserSkillStatus.ACTIVE,
        server_default=UserSkillStatus.ACTIVE.value,
        comment="技能画像状态：active 当前有效，archived 用户已归档。",
    )

    source: Mapped[UserSkillSource] = mapped_column(
        enum_column(UserSkillSource, name="user_skill_source", length=30),
        nullable=False,
        default=UserSkillSource.SELF_REPORTED,
        server_default=UserSkillSource.SELF_REPORTED.value,
        comment=(
            "技能来源：self_reported 用户自填，imported 导入，assessment 测评，inferred 系统推断。"
        ),
    )

    proficiency_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="掌握等级，1 入门，2 基础，3 可工作，4 熟练，5 专家。",
    )

    interest_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
        comment="学习意愿等级，1 最低，5 最高，用于后续学习任务排序。",
    )

    years_of_experience: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1),
        nullable=True,
        comment="该技能相关经验年限，可为空。",
    )

    last_used_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="用户最近一次实际使用该技能的日期。",
    )

    evidence: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="技能掌握证据，例如项目、证书、工作经历摘要。",
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="用户对该技能的补充备注。",
    )

    assessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="该技能等级最近一次被用户确认或系统评估的时间。",
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="技能画像归档时间。当前 active 时为空。",
    )

    user: Mapped[User] = relationship(
        back_populates="skill_profiles",
    )

    skill: Mapped[Skill] = relationship(
        back_populates="user_skill_profiles",
    )
