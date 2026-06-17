from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from job_pilot.core.contracts import PageQuery
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    JobPostStatus,
    WorkplaceType,
)

JobPostSort = Literal[
    "published_at_desc",
    "published_at_asc",
    "created_at_desc",
    "created_at_asc",
    "salary_max_desc",
    "salary_min_asc",
]


@dataclass(slots=True, frozen=True)
class JobPostSearchQuery(PageQuery):
    """岗位搜索内部查询参数。"""

    keyword: str | None = None
    source_platforms: list[str] | None = None
    statuses: list[JobPostStatus] | None = None
    employment_types: list[EmploymentType] | None = None
    workplace_types: list[WorkplaceType] | None = None
    experience_levels: list[ExperienceLevel] | None = None
    education_levels: list[EducationLevel] | None = None
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    locations: list[str] | None = None
    skill_ids: list[int] | None = None
    is_remote: bool | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    seen_from: datetime | None = None
    seen_to: datetime | None = None
    sort: JobPostSort = "published_at_desc"
    include_closed: bool = False
