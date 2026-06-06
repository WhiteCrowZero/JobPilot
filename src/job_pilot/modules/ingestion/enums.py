from __future__ import annotations

from enum import StrEnum


class RawJobRecordStatus(StrEnum):
    """原始岗位记录处理状态。"""

    RECEIVED = "received"
    NORMALIZED = "normalized"
    FAILED = "failed"
    SKIPPED = "skipped"
