from __future__ import annotations

from job_pilot.core.exceptions import NotFoundError


class JobPostForMatchNotFoundError(NotFoundError):
    """岗位不存在或已被删除。"""

    def __init__(self) -> None:
        super().__init__(
            message="Job post not found for skill coverage analysis",
            code="JOB_POST_FOR_MATCH_NOT_FOUND",
        )


class JobTargetForMatchNotFoundError(NotFoundError):
    """目标岗位不存在或不属于当前用户。"""

    def __init__(self) -> None:
        super().__init__(
            message="Job target not found for skill coverage analysis",
            code="JOB_TARGET_FOR_MATCH_NOT_FOUND",
        )
