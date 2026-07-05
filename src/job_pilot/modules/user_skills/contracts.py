from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from job_pilot.core.contracts import PageQuery
from job_pilot.modules.user_skills.enums import (
    UserSkillInterestLevel,
    UserSkillProficiencyLevel,
    UserSkillSource,
    UserSkillStatus,
)

UserSkillProficiencyValue = UserSkillProficiencyLevel | int
UserSkillInterestValue = UserSkillInterestLevel | int


@dataclass(slots=True, frozen=True)
class UserSkillUpsertCommand:
    """新增或恢复用户技能内部命令。"""

    skill_id: int
    source: UserSkillSource = UserSkillSource.SELF_REPORTED
    proficiency_level: UserSkillProficiencyValue = UserSkillProficiencyLevel.BEGINNER
    interest_level: UserSkillInterestValue = UserSkillInterestLevel.MEDIUM
    years_of_experience: Decimal | None = None
    last_used_at: date | None = None
    evidence: str | None = None
    note: str | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class UserSkillUpdateCommand:
    """更新用户技能内部命令。"""

    source: UserSkillSource | None = None
    proficiency_level: UserSkillProficiencyValue | None = None
    interest_level: UserSkillInterestValue | None = None
    years_of_experience: Decimal | None = None
    last_used_at: date | None = None
    evidence: str | None = None
    note: str | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class UserSkillListQuery(PageQuery):
    """用户技能列表内部查询参数。"""

    statuses: list[UserSkillStatus] | None = None
    skill_ids: list[int] | None = None
