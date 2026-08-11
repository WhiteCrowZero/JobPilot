from __future__ import annotations

from enum import StrEnum


class RawJobRecordStatus(StrEnum):
    """原始岗位记录处理状态。"""

    RECEIVED = "received"
    NORMALIZED = "normalized"
    FAILED = "failed"
    SKIPPED = "skipped"


class RawJobSkillSyncStatus(StrEnum):
    """原始岗位对应技能同步状态。"""

    NOT_STARTED = "not_started"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
