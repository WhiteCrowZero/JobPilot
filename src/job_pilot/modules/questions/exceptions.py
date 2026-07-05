from __future__ import annotations

from job_pilot.core.exceptions import NotFoundError


class QuestionNotFoundError(NotFoundError):
    """问题不存在。"""

    def __init__(self, message: str = "Question not found"):
        super().__init__(message=message, code="QUESTION_NOT_FOUND")
