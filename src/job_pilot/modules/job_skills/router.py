from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from job_pilot.api.deps import JobPilotDep
from job_pilot.core.pagination import PageParams
from job_pilot.modules.job_skills.schemas import SkillListParams, SkillListResponse

router = APIRouter()


@router.get("", response_model=SkillListResponse)
async def list_skills(
    pilot: JobPilotDep,
    pagination: Annotated[PageParams, Depends()],
    keyword: Annotated[str | None, Query(max_length=100)] = None,
) -> SkillListResponse:
    """查询标准技能字典。用户侧只返回 id 和 name。"""

    params = SkillListParams(
        keyword=keyword,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return await pilot.skills.list_skills(params)
