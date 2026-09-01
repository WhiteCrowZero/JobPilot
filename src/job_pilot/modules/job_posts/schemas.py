from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.core.schema_validators import (
    validate_business_datetime,
    validate_datetime_order,
)
from job_pilot.modules.job_posts.contracts import JobPostSort
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    JobPostStatus,
)
from job_pilot.modules.job_skills.schemas import SkillLabelResponse

PositiveId = Annotated[int, Field(gt=0)]
ShortQueryText = Annotated[str, Field(min_length=1, max_length=80)]


class JobPostSearchParams(PageParams):
    """岗位复杂筛选参数。"""

    keyword: str | None = Field(default=None, max_length=100)
    source_platforms: list[ShortQueryText] | None = Field(default=None, max_length=20)
    statuses: list[JobPostStatus] | None = Field(default=None, max_length=4)
    education_levels: list[EducationLevel] | None = Field(default=None, max_length=10)
    locations: list[ShortQueryText] | None = Field(default=None, max_length=50)
    skill_ids: list[PositiveId] | None = Field(default=None, max_length=50)
    published_from: datetime | None = None
    published_to: datetime | None = None
    sort: JobPostSort = "published_at_desc"

    @field_validator("published_from", "published_to")
    @classmethod
    def validate_time_bound(
        cls,
        value: datetime | None,
        info: ValidationInfo,
    ) -> datetime | None:
        return validate_business_datetime(value, field_name=info.field_name or "datetime")

    @model_validator(mode="after")
    def validate_ranges(self) -> JobPostSearchParams:
        validate_datetime_order(
            self.published_from,
            self.published_to,
            start_name="published_from",
            end_name="published_to",
        )
        return self


class JobPostListItem(BaseModel):
    """岗位列表项，保留列表页需要的高频字段。"""

    id: int
    source_platform: str
    source_name: str
    source_base_url: str
    title: str
    locations: str | None
    experience_text: str | None
    education_level: EducationLevel
    salary_text: str | None
    published_at: datetime | None
    created_at: datetime
    status: JobPostStatus


class JobPostListResponse(PageResult[JobPostListItem]):
    """岗位分页列表响应。"""


class JobPostDetailResponse(JobPostListItem):
    """岗位详情响应。"""

    source_url: str | None
    description: str | None
    skills: list[SkillLabelResponse] = Field(default_factory=list)


class JobPostFilterOptionsResponse(BaseModel):
    """岗位筛选项响应，供前端生成筛选控件。"""

    source_platforms: list[str] = Field(default_factory=list)
    statuses: list[JobPostStatus] = Field(default_factory=list)
    education_levels: list[EducationLevel] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    skills: list[SkillLabelResponse] = Field(default_factory=list)
