from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from job_pilot.api.deps import CurrentActiveUserDep, DbSessionDep
from job_pilot.core.pagination import PageParams
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
from job_pilot.modules.job_collections.service import build_job_collection_service

router = APIRouter()
service = build_job_collection_service()


@router.post("/folders", response_model=JobCollectionFolderResponse)
async def create_collection_folder(
    payload: JobCollectionFolderCreate,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> JobCollectionFolderResponse:
    """创建当前用户岗位收藏夹。"""

    return await service.create_folder(
        session,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/folders", response_model=list[JobCollectionFolderResponse])
async def list_collection_folders(
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> list[JobCollectionFolderResponse]:
    """查询当前用户岗位收藏夹。"""

    return await service.list_folders(session, user_id=current_user.id)


@router.patch("/folders/{folder_id}", response_model=JobCollectionFolderResponse)
async def update_collection_folder(
    folder_id: int,
    payload: JobCollectionFolderUpdate,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> JobCollectionFolderResponse:
    """更新当前用户岗位收藏夹。"""

    return await service.update_folder(
        session,
        user_id=current_user.id,
        folder_id=folder_id,
        payload=payload,
    )


@router.post("/folders/{folder_id}/default", response_model=JobCollectionFolderResponse)
async def set_default_collection_folder(
    folder_id: int,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> JobCollectionFolderResponse:
    """设置当前用户默认岗位收藏夹。"""

    return await service.set_default_folder(
        session,
        user_id=current_user.id,
        folder_id=folder_id,
    )


@router.delete("/folders/{folder_id}", response_model=JobCollectionFolderResponse)
async def archive_collection_folder(
    folder_id: int,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> JobCollectionFolderResponse:
    """归档当前用户岗位收藏夹。"""

    return await service.archive_folder(
        session,
        user_id=current_user.id,
        folder_id=folder_id,
    )


@router.post("", response_model=JobCollectionResponse)
async def collect_job(
    payload: JobCollectionCreate,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> JobCollectionResponse:
    """收藏或恢复当前用户岗位收藏。"""

    return await service.collect_job(
        session,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("", response_model=JobCollectionListResponse)
async def list_collections(
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
    pagination: Annotated[PageParams, Depends()],
    include_removed: bool = False,
    folder_id: int | None = None,
) -> JobCollectionListResponse:
    """查询当前用户岗位收藏。"""

    params = JobCollectionListParams(
        include_removed=include_removed,
        folder_id=folder_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return await service.list_collections(
        session,
        user_id=current_user.id,
        params=params,
    )


@router.patch("/{collection_id}", response_model=JobCollectionResponse)
async def update_collection(
    collection_id: int,
    payload: JobCollectionUpdate,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> JobCollectionResponse:
    """更新当前用户岗位收藏。"""

    return await service.update_collection(
        session,
        user_id=current_user.id,
        collection_id=collection_id,
        payload=payload,
    )


@router.delete("/{collection_id}", response_model=JobCollectionResponse)
async def remove_collection(
    collection_id: int,
    session: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> JobCollectionResponse:
    """软取消当前用户岗位收藏。"""

    return await service.remove_collection(
        session,
        user_id=current_user.id,
        collection_id=collection_id,
    )
