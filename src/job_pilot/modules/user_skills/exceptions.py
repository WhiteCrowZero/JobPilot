from __future__ import annotations

from job_pilot.core.exceptions import NotFoundError


class StandardSkillNotFoundError(NotFoundError):
    """标准技能不存在。"""

    def __init__(self, message: str = "Standard skill not found"):
        super().__init__(message=message, code="STANDARD_SKILL_NOT_FOUND")


class UserSkillNotFoundError(NotFoundError):
    """用户技能画像不存在。"""

    def __init__(self, message: str = "User skill profile not found"):
        super().__init__(message=message, code="USER_SKILL_NOT_FOUND")
