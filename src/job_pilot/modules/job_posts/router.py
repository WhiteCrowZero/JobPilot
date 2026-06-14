from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from job_pilot.api.deps import CurrentCacheStoreDep, DbSessionDep
from job_pilot.core.pagination import PageParams
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    JobPostStatus,
    WorkplaceType,
)
from job_pilot.modules.job_posts.schemas import (
    JobPostDetailResponse,
    JobPostFilterOptionsResponse,
    JobPostListResponse,
    JobPostSearchParams,
    JobPostSort,
)
from job_pilot.modules.job_posts.service import build_job_post_service

router = APIRouter()
service = build_job_post_service()


@router.get("/search", response_model=JobPostListResponse)
async def search_job_posts(
    session: DbSessionDep,
    pagination: Annotated[PageParams, Depends()],
    keyword: Annotated[str | None, Query(max_length=100)] = None,
    source_platforms: Annotated[list[str] | None, Query()] = None,
    statuses: Annotated[list[JobPostStatus] | None, Query()] = None,
    employment_types: Annotated[list[EmploymentType] | None, Query()] = None,
    workplace_types: Annotated[list[WorkplaceType] | None, Query()] = None,
    experience_levels: Annotated[list[ExperienceLevel] | None, Query()] = None,
    education_levels: Annotated[list[EducationLevel] | None, Query()] = None,
    experience_min_years: Annotated[int | None, Query(ge=0, le=80)] = None,
    experience_max_years: Annotated[int | None, Query(ge=0, le=80)] = None,
    salary_min: Annotated[int | None, Query(ge=0)] = None,
    salary_max: Annotated[int | None, Query(ge=0)] = None,
    salary_currency: Annotated[str | None, Query(max_length=10)] = None,
    locations: Annotated[list[str] | None, Query()] = None,
    skill_ids: Annotated[list[int] | None, Query()] = None,
    is_remote: bool | None = None,
    published_from: datetime | None = None,
    published_to: datetime | None = None,
    seen_from: datetime | None = None,
    seen_to: datetime | None = None,
    sort: JobPostSort = "published_at_desc",
    include_closed: bool = False,
) -> JobPostListResponse:
    """查询岗位列表，支持关键词、枚举、薪资、地点文本和时间范围筛选。"""

    params = JobPostSearchParams(
        keyword=keyword,
        source_platforms=source_platforms,
        statuses=statuses,
        employment_types=employment_types,
        workplace_types=workplace_types,
        experience_levels=experience_levels,
        education_levels=education_levels,
        experience_min_years=experience_min_years,
        experience_max_years=experience_max_years,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        locations=locations,
        skill_ids=skill_ids,
        is_remote=is_remote,
        published_from=published_from,
        published_to=published_to,
        seen_from=seen_from,
        seen_to=seen_to,
        sort=sort,
        page=pagination.page,
        page_size=pagination.page_size,
        include_closed=include_closed,
    )
    return await service.search_job_posts(session, params)


@router.get("/filter-options", response_model=JobPostFilterOptionsResponse)
async def read_job_post_filter_options(
    session: DbSessionDep,
    cache: CurrentCacheStoreDep,
) -> JobPostFilterOptionsResponse:
    """读取岗位筛选项候选值。"""

    return await service.get_filter_options(session, cache)


@router.get("/{job_post_id}", response_model=JobPostDetailResponse)
async def read_job_post_detail(job_post_id: int, session: DbSessionDep) -> JobPostDetailResponse:
    """读取岗位详情。"""

    return await service.get_job_post_detail(session, job_post_id)
