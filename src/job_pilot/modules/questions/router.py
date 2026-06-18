from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


# @router.get("/search", response_model=JobPostListResponse)
# async def search_job_posts(
#     pilot: JobPilotDep,
#     params: Annotated[JobPostSearchParams, Query()],
# ) -> JobPostListResponse:
#     """查询岗位列表，支持关键词、枚举、薪资、地点文本和时间范围筛选。"""
#
#     query = JobPostSearchQuery(**params.model_dump())
#     return await pilot.job_posts.search(query)
#
#
# @router.get("/{question_id}", response_model=JobPostDetailResponse)
# async def read_job_post_detail(job_post_id: int, pilot: JobPilotDep) -> JobPostDetailResponse:
#     """读取岗位详情。"""
#
#     return await pilot.job_posts.get_detail(job_post_id=job_post_id)
