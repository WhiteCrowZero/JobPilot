from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from job_pilot.api.deps import JobPilotDep
from job_pilot.modules.job_skills.schemas import SkillListParams, SkillListResponse

router = APIRouter()


@router.get("", response_model=SkillListResponse)
async def list_skills(
    pilot: JobPilotDep,
    params: Annotated[SkillListParams, Query()],
) -> SkillListResponse:
    """查询标准技能字典。用户侧只返回 id 和 name。"""

    return await pilot.skills.list_skills(params)
