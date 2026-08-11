from __future__ import annotations

from enum import StrEnum


class KnownJobSourcePlatform(StrEnum):
    """代码层已知来源标识。"""

    ALIBABA = "alibaba"
    TENCENT = "tencent"
    JAABZ = "jaabz"
    SAMPLE = "sample"
    MOCK = "mock"


class JobPostStatus(StrEnum):
    """规范化岗位状态。"""

    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    """雇佣类型。"""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    FREELANCE = "freelance"
    UNKNOWN = "unknown"


class WorkplaceType(StrEnum):
    """工作地点/办公方式类型。"""

    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class ExperienceLevel(StrEnum):
    """经验等级。"""

    INTERN = "intern"
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    DIRECTOR = "director"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class EducationLevel(StrEnum):
    """学历等级。"""

    NONE = "none"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTOR = "doctor"
    UNKNOWN = "unknown"


class SalaryPeriod(StrEnum):
    """薪资周期。"""

    HOUR = "hour"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"
