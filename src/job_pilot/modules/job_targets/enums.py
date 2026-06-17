from __future__ import annotations

from enum import StrEnum


class JobTargetStatus(StrEnum):
    """目标岗位准备状态。"""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"
