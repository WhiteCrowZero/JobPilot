from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from job_pilot.api.deps import CurrentActiveUserDep, JobPilotDep
from job_pilot.core.pagination import PageParams
from job_pilot.modules.job_targets.enums import JobTargetStatus
from job_pilot.modules.job_targets.schemas import (
    JobTargetCreate,
    JobTargetListParams,
    JobTargetListResponse,
    JobTargetResponse,
    JobTargetUpdate,
)

router = APIRouter()


@router.post("", response_model=JobTargetResponse)
async def create_target(
    payload: JobTargetCreate,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobTargetResponse:
    """新增或恢复当前用户目标岗位。"""

    return await pilot.workbench.create_target(
        user_id=current_user.id,
        payload=payload,
    )


@router.get("", response_model=JobTargetListResponse)
async def list_targets(
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
    pagination: Annotated[PageParams, Depends()],
    statuses: Annotated[list[JobTargetStatus] | None, Query()] = None,
) -> JobTargetListResponse:
    """查询当前用户目标岗位。"""

    params = JobTargetListParams(
        statuses=statuses,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return await pilot.workbench.list_targets(
        user_id=current_user.id,
        params=params,
    )


@router.patch("/{target_id}", response_model=JobTargetResponse)
async def update_target(
    target_id: int,
    payload: JobTargetUpdate,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobTargetResponse:
    """更新当前用户目标岗位。"""

    return await pilot.workbench.update_target(
        user_id=current_user.id,
        target_id=target_id,
        payload=payload,
    )


@router.delete("/{target_id}", response_model=JobTargetResponse)
async def archive_target(
    target_id: int,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobTargetResponse:
    """归档当前用户目标岗位。"""

    return await pilot.workbench.archive_target(
        user_id=current_user.id,
        target_id=target_id,
    )
