from __future__ import annotations

from enum import StrEnum


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
