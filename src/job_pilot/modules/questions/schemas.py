from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.modules.job_posts.contracts import JobPostSort
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    JobPostStatus,
    SalaryPeriod,
    WorkplaceType,
)
from job_pilot.modules.job_skills.schemas import SkillLabelResponse


class JobPostSearchParams(PageParams):
    """岗位复杂筛选参数。"""

    keyword: str | None = Field(default=None, max_length=100)
    source_platforms: list[str] | None = None
    statuses: list[JobPostStatus] | None = None
    employment_types: list[EmploymentType] | None = None
    workplace_types: list[WorkplaceType] | None = None
    experience_levels: list[ExperienceLevel] | None = None
    education_levels: list[EducationLevel] | None = None
    experience_min_years: int | None = Field(default=None, ge=0, le=80)
    experience_max_years: int | None = Field(default=None, ge=0, le=80)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=10)
    locations: list[str] | None = None
    skill_ids: list[int] | None = None
    is_remote: bool | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    seen_from: datetime | None = None
    seen_to: datetime | None = None
    sort: JobPostSort = "published_at_desc"
    include_closed: bool = False

    @model_validator(mode="after")
    def validate_ranges(self) -> JobPostSearchParams:
        if self.experience_min_years is not None and self.experience_max_years is not None:
            if self.experience_min_years > self.experience_max_years:
                raise ValueError("experience_min_years must be <= experience_max_years")
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min > self.salary_max:
                raise ValueError("salary_min must be <= salary_max")
        return self


class JobPostListItem(BaseModel):
    """岗位列表项，保留列表页需要的高频字段。"""

    id: int
    source_platform: str
    source_name: str
    source_base_url: str
    title: str
    company_name: str | None
    locations: str | None
    is_remote: bool
    employment_type: EmploymentType
    workplace_type: WorkplaceType
    experience_level: ExperienceLevel
    education_level: EducationLevel
    salary_text: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    salary_period: SalaryPeriod
    published_at: datetime | None
    created_at: datetime
    status: JobPostStatus


class JobPostListResponse(PageResult[JobPostListItem]):
    """岗位分页列表响应。"""


class JobPostDetailResponse(JobPostListItem):
    """岗位详情响应，包含详情页冷字段。"""

    source_url: str | None
    company_url: str | None
    description: str | None
    has_visa_sponsorship: bool | None
    has_relocation_support: bool | None
    work_authorization_note: str | None
    skills: list[SkillLabelResponse] = Field(default_factory=list)


class JobPostFilterOptionsResponse(BaseModel):
    """岗位筛选项响应，供前端生成筛选控件。"""

    source_platforms: list[str] = Field(default_factory=list)
    statuses: list[JobPostStatus] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    workplace_types: list[WorkplaceType] = Field(default_factory=list)
    experience_levels: list[ExperienceLevel] = Field(default_factory=list)
    education_levels: list[EducationLevel] = Field(default_factory=list)
    salary_currencies: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    skills: list[SkillLabelResponse] = Field(default_factory=list)
