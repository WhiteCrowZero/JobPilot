from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from job_pilot.api.deps import CurrentActiveUserDep, DbSessionDep
from job_pilot.core.pagination import PageParams
from job_pilot.modules.user_skills.schemas import (
    UserSkillListParams,
    UserSkillListResponse,
    UserSkillResponse,
    UserSkillUpdate,
    UserSkillUpsert,
)
from job_pilot.modules.user_skills.service import build_user_skill_service

router = APIRouter()
service = build_user_skill_service()


@router.post("", response_model=UserSkillResponse)
async def upsert_user_skill(
    payload: UserSkillUpsert,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> UserSkillResponse:
    """新增或恢复当前用户技能画像。"""

    return await service.upsert_user_skill(
        session,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("", response_model=UserSkillListResponse)
async def list_user_skills(
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
    pagination: Annotated[PageParams, Depends()],
    include_archived: bool = False,
    skill_ids: Annotated[list[int] | None, Query()] = None,
) -> UserSkillListResponse:
    """查询当前用户技能画像列表。"""

    params = UserSkillListParams(
        include_archived=include_archived,
        skill_ids=skill_ids,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return await service.list_user_skills(
        session,
        user_id=current_user.id,
        params=params,
    )


@router.patch("/{skill_id}", response_model=UserSkillResponse)
async def update_user_skill(
    skill_id: int,
    payload: UserSkillUpdate,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> UserSkillResponse:
    """更新当前用户技能画像。"""

    return await service.update_user_skill(
        session,
        user_id=current_user.id,
        skill_id=skill_id,
        payload=payload,
    )


@router.delete("/{skill_id}", response_model=UserSkillResponse)
async def archive_user_skill(
    skill_id: int,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> UserSkillResponse:
    """归档当前用户技能画像。"""

    return await service.archive_user_skill(
        session,
        user_id=current_user.id,
        skill_id=skill_id,
    )
