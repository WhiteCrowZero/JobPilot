from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.modules.user_skills.enums import UserSkillSource, UserSkillStatus


class UserSkillUpsert(BaseModel):
    """新增或恢复用户技能画像请求。"""

    skill_id: int = Field(gt=0)
    source: UserSkillSource = UserSkillSource.SELF_REPORTED
    proficiency_level: int = Field(default=1, ge=1, le=5)
    interest_level: int = Field(default=3, ge=1, le=5)
    years_of_experience: Decimal | None = Field(default=None, ge=0, max_digits=4, decimal_places=1)
    last_used_at: date | None = None
    evidence: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)


class UserSkillUpdate(BaseModel):
    """局部更新用户技能画像请求。"""

    source: UserSkillSource | None = None
    proficiency_level: int | None = Field(default=None, ge=1, le=5)
    interest_level: int | None = Field(default=None, ge=1, le=5)
    years_of_experience: Decimal | None = Field(default=None, ge=0, max_digits=4, decimal_places=1)
    last_used_at: date | None = None
    evidence: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)


class UserSkillListParams(PageParams):
    """用户技能画像列表查询参数。"""

    include_archived: bool = False
    skill_ids: list[int] | None = None


class UserSkillResponse(BaseModel):
    """用户技能画像响应。"""

    id: int
    user_id: int
    skill_id: int
    status: UserSkillStatus
    source: UserSkillSource
    proficiency_level: int
    interest_level: int
    years_of_experience: Decimal | None
    last_used_at: date | None
    evidence: str | None
    note: str | None
    assessed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserSkillListResponse(PageResult[UserSkillResponse]):
    """用户技能画像分页响应。"""
