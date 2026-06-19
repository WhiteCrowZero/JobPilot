from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from job_pilot.api.deps import CurrentActiveUserDep, JobPilotDep
from job_pilot.modules.user_skills.contracts import (
    UserSkillListQuery,
    UserSkillUpdateCommand,
    UserSkillUpsertCommand,
)
from job_pilot.modules.user_skills.schemas import (
    UserSkillListParams,
    UserSkillListResponse,
    UserSkillResponse,
    UserSkillUpdate,
    UserSkillUpsert,
)

router = APIRouter()


@router.post("", response_model=UserSkillResponse)
async def upsert_user_skill(
    payload: UserSkillUpsert,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> UserSkillResponse:
    """新增或恢复当前用户技能画像。"""

    return await pilot.workbench.upsert_user_skill(
        user_id=current_user.id,
        payload=UserSkillUpsertCommand(
            skill_id=payload.skill_id,
            source=payload.source,
            proficiency_level=payload.proficiency_level,
            interest_level=payload.interest_level,
            years_of_experience=payload.years_of_experience,
            last_used_at=payload.last_used_at,
            evidence=payload.evidence,
            note=payload.note,
            fields_set=frozenset(payload.model_fields_set),
        ),
    )


@router.get("", response_model=UserSkillListResponse)
async def list_user_skills(
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
    params: Annotated[UserSkillListParams, Query()],
) -> UserSkillListResponse:
    """查询当前用户技能画像列表。"""

    query = UserSkillListQuery(
        statuses=params.statuses,
        skill_ids=params.skill_ids,
        page=params.page,
        page_size=params.page_size,
    )
    return await pilot.workbench.list_user_skills(
        user_id=current_user.id,
        params=query,
    )


@router.patch("/{skill_id}", response_model=UserSkillResponse)
async def update_user_skill(
    skill_id: Annotated[int, Path(gt=0)],
    payload: UserSkillUpdate,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> UserSkillResponse:
    """更新当前用户技能画像。"""

    return await pilot.workbench.update_user_skill(
        user_id=current_user.id,
        skill_id=skill_id,
        payload=UserSkillUpdateCommand(
            source=payload.source,
            proficiency_level=payload.proficiency_level,
            interest_level=payload.interest_level,
            years_of_experience=payload.years_of_experience,
            last_used_at=payload.last_used_at,
            evidence=payload.evidence,
            note=payload.note,
            fields_set=frozenset(payload.model_fields_set),
        ),
    )


@router.delete("/{skill_id}", response_model=UserSkillResponse)
async def archive_user_skill(
    skill_id: Annotated[int, Path(gt=0)],
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> UserSkillResponse:
    """归档当前用户技能画像。"""

    return await pilot.workbench.archive_user_skill(
        user_id=current_user.id,
        skill_id=skill_id,
    )
