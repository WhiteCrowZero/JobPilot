from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.modules.job_targets.enums import JobTargetStatus


class JobTargetCreate(BaseModel):
    """新增或恢复目标岗位请求。"""

    job_post_id: int = Field(gt=0)
    source_collection_id: int | None = Field(default=None, gt=0)
    priority: int = Field(default=3, ge=1, le=5)
    is_primary: bool = False
    note: str | None = Field(default=None, max_length=500)
    target_date: date | None = None


class JobTargetUpdate(BaseModel):
    """局部更新目标岗位请求。"""

    status: JobTargetStatus | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    is_primary: bool | None = None
    note: str | None = Field(default=None, max_length=500)
    target_date: date | None = None


class JobTargetListParams(PageParams):
    """目标岗位列表查询参数。"""

    statuses: list[JobTargetStatus] | None = None


class JobTargetResponse(BaseModel):
    """目标岗位响应。"""

    id: int
    user_id: int
    job_post_id: int
    source_collection_id: int | None
    status: JobTargetStatus
    priority: int
    is_primary: bool
    note: str | None
    target_date: date | None
    targeted_at: datetime
    completed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobTargetListResponse(PageResult[JobTargetResponse]):
    """目标岗位分页响应。"""
