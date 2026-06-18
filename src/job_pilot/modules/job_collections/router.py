from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from job_pilot.api.deps import CurrentActiveUserDep, JobPilotDep
from job_pilot.modules.job_collections.contracts import (
    JobCollectionCreateCommand,
    JobCollectionFolderCreateCommand,
    JobCollectionFolderUpdateCommand,
    JobCollectionListQuery,
    JobCollectionUpdateCommand,
)
from job_pilot.modules.job_collections.schemas import (
    JobCollectionCreate,
    JobCollectionFolderCreate,
    JobCollectionFolderResponse,
    JobCollectionFolderUpdate,
    JobCollectionListParams,
    JobCollectionListResponse,
    JobCollectionResponse,
    JobCollectionUpdate,
)

router = APIRouter()


@router.post("/folders", response_model=JobCollectionFolderResponse)
async def create_collection_folder(
    payload: JobCollectionFolderCreate,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobCollectionFolderResponse:
    """创建当前用户岗位收藏夹。"""

    return await pilot.workbench.create_collection_folder(
        user_id=current_user.id,
        payload=JobCollectionFolderCreateCommand(
            name=payload.name,
            sort_order=payload.sort_order,
        ),
    )


@router.get("/folders", response_model=list[JobCollectionFolderResponse])
async def list_collection_folders(
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> list[JobCollectionFolderResponse]:
    """查询当前用户岗位收藏夹。"""

    return await pilot.workbench.list_collection_folders(user_id=current_user.id)


@router.patch("/folders/{folder_id}", response_model=JobCollectionFolderResponse)
async def update_collection_folder(
    folder_id: int,
    payload: JobCollectionFolderUpdate,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobCollectionFolderResponse:
    """更新当前用户岗位收藏夹。"""

    return await pilot.workbench.update_collection_folder(
        user_id=current_user.id,
        folder_id=folder_id,
        payload=JobCollectionFolderUpdateCommand(
            name=payload.name,
            sort_order=payload.sort_order,
            fields_set=frozenset(payload.model_fields_set),
        ),
    )


@router.post("/folders/{folder_id}/default", response_model=JobCollectionFolderResponse)
async def set_default_collection_folder(
    folder_id: int,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobCollectionFolderResponse:
    """设置当前用户默认岗位收藏夹。"""

    return await pilot.workbench.set_default_collection_folder(
        user_id=current_user.id,
        folder_id=folder_id,
    )


@router.delete("/folders/{folder_id}", response_model=JobCollectionFolderResponse)
async def archive_collection_folder(
    folder_id: int,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobCollectionFolderResponse:
    """归档当前用户岗位收藏夹。"""

    return await pilot.workbench.archive_collection_folder(
        user_id=current_user.id,
        folder_id=folder_id,
    )


@router.post("", response_model=JobCollectionResponse)
async def collect_job(
    payload: JobCollectionCreate,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobCollectionResponse:
    """收藏或恢复当前用户岗位收藏。"""

    return await pilot.workbench.collect_job(
        user_id=current_user.id,
        payload=JobCollectionCreateCommand(
            job_post_id=payload.job_post_id,
            folder_id=payload.folder_id,
            note=payload.note,
            fields_set=frozenset(payload.model_fields_set),
        ),
    )


@router.get("", response_model=JobCollectionListResponse)
async def list_collections(
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
    params: Annotated[JobCollectionListParams, Query()],
) -> JobCollectionListResponse:
    """查询当前用户岗位收藏。"""

    query = JobCollectionListQuery(
        include_removed=params.include_removed,
        folder_id=params.folder_id,
        page=params.page,
        page_size=params.page_size,
    )
    return await pilot.workbench.list_collections(
        user_id=current_user.id,
        params=query,
    )


@router.patch("/{collection_id}", response_model=JobCollectionResponse)
async def update_collection(
    collection_id: int,
    payload: JobCollectionUpdate,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobCollectionResponse:
    """更新当前用户岗位收藏。"""

    return await pilot.workbench.update_collection(
        user_id=current_user.id,
        collection_id=collection_id,
        payload=JobCollectionUpdateCommand(
            folder_id=payload.folder_id,
            note=payload.note,
            fields_set=frozenset(payload.model_fields_set),
        ),
    )


@router.delete("/{collection_id}", response_model=JobCollectionResponse)
async def remove_collection(
    collection_id: int,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> JobCollectionResponse:
    """软取消当前用户岗位收藏。"""

    return await pilot.workbench.remove_collection(
        user_id=current_user.id,
        collection_id=collection_id,
    )
