from __future__ import annotations

from job_pilot.core.exceptions import BadRequestError, NotFoundError


class KnowledgePointNotFoundError(NotFoundError):
    """知识点不存在。"""

    def __init__(self, message: str = "Knowledge point not found"):
        super().__init__(message=message, code="KNOWLEDGE_POINT_NOT_FOUND")


class KnowledgeTreeScopeMismatchError(BadRequestError):
    """知识点树查询范围不匹配。"""

    def __init__(self, message: str = "Knowledge tree scope mismatch"):
        super().__init__(message=message, code="KNOWLEDGE_TREE_SCOPE_MISMATCH")
