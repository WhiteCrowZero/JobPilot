from __future__ import annotations

from job_pilot.core.exceptions import NotFoundError, ValidationError


class JobPostForTargetNotFoundError(NotFoundError):
    """目标岗位对应的岗位不存在。"""

    def __init__(self, message: str = "Job post not found for target"):
        super().__init__(message=message, code="JOB_TARGET_JOB_POST_NOT_FOUND")


class JobTargetNotFoundError(NotFoundError):
    """目标岗位不存在。"""

    def __init__(self, message: str = "Job target not found"):
        super().__init__(message=message, code="JOB_TARGET_NOT_FOUND")


class JobTargetSourceCollectionInvalidError(ValidationError):
    """来源收藏不存在、无权访问或与岗位不匹配。"""

    def __init__(self, message: str = "Source collection is invalid for target"):
        super().__init__(
            message=message,
            code="JOB_TARGET_SOURCE_COLLECTION_INVALID",
        )
