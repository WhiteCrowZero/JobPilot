from __future__ import annotations

from job_pilot.core.exceptions import NotFoundError


class KnowledgePointNotFoundError(NotFoundError):
    """知识点不存在。"""

    def __init__(self, message: str = "Knowledge point not found"):
        super().__init__(message=message, code="STANDARD_SKILL_NOT_FOUND")
