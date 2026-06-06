from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    WorkplaceType,
)


@dataclass(slots=True, frozen=True)
class NormalizedLocation:
    """MVP 地点归一结果。

    不再拆国家、城市、区域；只保留展示/搜索用 locations 文本和远程标记。
    """

    locations: str | None
    is_remote: bool


@dataclass(slots=True, frozen=True)
class NormalizedSalary:
    """规范化后的薪资范围。

    周期语义暂时只保留在 salary_text；避免清洗不准时制造伪结构化字段。
    """

    salary_text: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str


@dataclass(slots=True, frozen=True)
class NormalizedExperience:
    """规范化后的经验要求。"""

    experience_level: ExperienceLevel
    experience_min_years: int | None
    experience_max_years: int | None


@dataclass(slots=True, frozen=True)
class NormalizedMobility:
    """规范化后的海外流动性信息。"""

    has_visa_sponsorship: bool
    has_relocation_support: bool
    work_authorization_note: str | None


@dataclass(slots=True, frozen=True)
class NormalizedJob:
    """岗位草稿清洗后的统一结构，供 ingestion service 落库使用。"""

    fingerprint: str
    title: str
    company_name: str | None
    company_url: str | None
    source_url: str | None
    description: str | None
    locations: str | None
    is_remote: bool
    employment_type: EmploymentType
    workplace_type: WorkplaceType
    experience_level: ExperienceLevel
    experience_min_years: int | None
    experience_max_years: int | None
    education_level: EducationLevel
    salary_text: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    published_at: datetime | None
    has_visa_sponsorship: bool
    has_relocation_support: bool
    work_authorization_note: str | None
