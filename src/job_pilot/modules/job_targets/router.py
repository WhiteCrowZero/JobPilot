from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from job_pilot.api.deps import CurrentActiveUserDep, JobPilotDep
from job_pilot.modules.job_targets.contracts import (
    JobTargetCreateCommand,
    JobTargetListQuery,
    JobTargetUpdateCommand,
)
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
        payload=JobTargetCreateCommand(
            job_post_id=payload.job_post_id,
            source_collection_id=payload.source_collection_id,
            priority=payload.priority,
            is_primary=payload.is_primary,
            note=payload.note,
            target_date=payload.target_date,
            fields_set=frozenset(payload.model_fields_set),
        ),
    )


@router.get("", response_model=JobTargetListResponse)
async def list_targets(
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
    params: Annotated[JobTargetListParams, Query()],
) -> JobTargetListResponse:
    """查询当前用户目标岗位。"""

    query = JobTargetListQuery(
        statuses=params.statuses,
        page=params.page,
        page_size=params.page_size,
    )
    return await pilot.workbench.list_targets(
        user_id=current_user.id,
        params=query,
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
        payload=JobTargetUpdateCommand(
            status=payload.status,
            priority=payload.priority,
            is_primary=payload.is_primary,
            note=payload.note,
            target_date=payload.target_date,
            fields_set=frozenset(payload.model_fields_set),
        ),
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
