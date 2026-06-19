from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from job_pilot.api.deps import JobPilotDep
from job_pilot.modules.job_posts.contracts import JobPostSearchQuery
from job_pilot.modules.job_posts.schemas import (
    JobPostDetailResponse,
    JobPostFilterOptionsResponse,
    JobPostListResponse,
    JobPostSearchParams,
)

router = APIRouter()


@router.get("/search", response_model=JobPostListResponse)
async def search_job_posts(
    pilot: JobPilotDep,
    params: Annotated[JobPostSearchParams, Query()],
) -> JobPostListResponse:
    """查询岗位列表，支持关键词、枚举、薪资、地点文本和时间范围筛选。"""

    query = JobPostSearchQuery(**params.model_dump())
    return await pilot.job_posts.search(query)


@router.get("/filter-options", response_model=JobPostFilterOptionsResponse)
async def read_job_post_filter_options(
    pilot: JobPilotDep,
) -> JobPostFilterOptionsResponse:
    """读取岗位筛选项候选值。"""

    return await pilot.job_posts.get_filter_options()


@router.get("/{job_post_id}", response_model=JobPostDetailResponse)
async def read_job_post_detail(
    job_post_id: Annotated[int, Path(gt=0)],
    pilot: JobPilotDep,
) -> JobPostDetailResponse:
    """读取岗位详情。"""

    return await pilot.job_posts.get_detail(job_post_id=job_post_id)
