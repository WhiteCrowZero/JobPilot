from __future__ import annotations

from enum import IntEnum, StrEnum


class UserSkillStatus(StrEnum):
    """用户技能画像状态。"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class UserSkillSource(StrEnum):
    """用户技能来源。"""

    SELF_REPORTED = "self_reported"
    IMPORTED = "imported"
    ASSESSMENT = "assessment"
    INFERRED = "inferred"


class UserSkillProficiencyLevel(IntEnum):
    """用户技能掌握等级。"""

    BEGINNER = 1
    BASIC = 2
    WORK_READY = 3
    PROFICIENT = 4
    EXPERT = 5


class UserSkillInterestLevel(IntEnum):
    """用户技能学习意愿等级。"""

    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5
