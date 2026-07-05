from __future__ import annotations

from job_pilot.core.exceptions import NotFoundError


class JobPostForSkillSyncNotFoundError(NotFoundError):
    """岗位技能同步时目标岗位不存在。"""

    def __init__(self, message: str = "Job post not found") -> None:
        super().__init__(message=message, code="JOB_POST_NOT_FOUND")
