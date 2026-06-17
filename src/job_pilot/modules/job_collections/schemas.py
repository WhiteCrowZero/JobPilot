from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.modules.job_collections.enums import (
    JobCollectionFolderStatus,
    JobCollectionStatus,
)


class JobCollectionFolderCreate(BaseModel):
    """创建岗位收藏夹请求。"""

    name: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(default=99, ge=0)


class JobCollectionFolderUpdate(BaseModel):
    """局部更新岗位收藏夹请求。"""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    sort_order: int | None = Field(default=None, ge=0)


class JobCollectionFolderResponse(BaseModel):
    """岗位收藏夹响应。"""

    id: int
    user_id: int
    name: str
    status: JobCollectionFolderStatus
    is_default: bool
    sort_order: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobCollectionCreate(BaseModel):
    """收藏岗位请求。"""

    job_post_id: int = Field(gt=0)
    folder_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


class JobCollectionUpdate(BaseModel):
    """局部更新岗位收藏请求。"""

    folder_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


class JobCollectionListParams(PageParams):
    """岗位收藏列表查询参数。"""

    include_removed: bool = False
    folder_id: int | None = Field(default=None, gt=0)


class JobCollectionResponse(BaseModel):
    """岗位收藏响应。"""

    id: int
    user_id: int
    job_post_id: int
    folder_id: int | None
    status: JobCollectionStatus
    note: str | None
    collected_at: datetime
    removed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobCollectionListResponse(PageResult[JobCollectionResponse]):
    """岗位收藏分页响应。"""
