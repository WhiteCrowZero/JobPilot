from __future__ import annotations

from job_pilot.modules.job_targets.enums import JobTargetStatus

CURRENT_TARGET_STATUSES: tuple[JobTargetStatus, JobTargetStatus] = (
    JobTargetStatus.ACTIVE,
    JobTargetStatus.PAUSED,
)


def is_current_target_status(status: JobTargetStatus) -> bool:
    """判断目标岗位状态是否属于当前准备范围。"""

    return status in CURRENT_TARGET_STATUSES
