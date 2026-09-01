from __future__ import annotations

from enum import StrEnum


class KnownJobSourcePlatform(StrEnum):
    """代码层已知来源标识。"""

    TAOTIAN = "taotian"
    TENCENT = "tencent"
    SAMPLE = "sample"
    MOCK = "mock"


class JobPostStatus(StrEnum):
    """规范化岗位状态。"""

    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class EducationLevel(StrEnum):
    """学历等级。"""

    NONE = "none"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTOR = "doctor"
    UNKNOWN = "unknown"
