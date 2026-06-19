from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.core.schema_validators import validate_past_or_today_date
from job_pilot.modules.user_skills.enums import (
    UserSkillInterestLevel,
    UserSkillProficiencyLevel,
    UserSkillSource,
    UserSkillStatus,
)

PositiveId = Annotated[int, Field(gt=0)]


class UserSkillUpsert(BaseModel):
    """新增或恢复用户技能画像请求。"""

    skill_id: int = Field(gt=0)
    source: UserSkillSource = UserSkillSource.SELF_REPORTED
    proficiency_level: UserSkillProficiencyLevel = UserSkillProficiencyLevel.BEGINNER
    interest_level: UserSkillInterestLevel = UserSkillInterestLevel.MEDIUM
    years_of_experience: Decimal | None = Field(
        default=None,
        ge=0,
        le=Decimal("80.0"),
        max_digits=4,
        decimal_places=1,
    )
    last_used_at: date | None = None
    evidence: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("last_used_at")
    @classmethod
    def validate_last_used_at(
        cls,
        value: date | None,
        info: ValidationInfo,
    ) -> date | None:
        return validate_past_or_today_date(value, field_name=info.field_name or "last_used_at")


class UserSkillUpdate(BaseModel):
    """局部更新用户技能画像请求。"""

    source: UserSkillSource | None = None
    proficiency_level: UserSkillProficiencyLevel | None = None
    interest_level: UserSkillInterestLevel | None = None
    years_of_experience: Decimal | None = Field(
        default=None,
        ge=0,
        le=Decimal("80.0"),
        max_digits=4,
        decimal_places=1,
    )
    last_used_at: date | None = None
    evidence: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("last_used_at")
    @classmethod
    def validate_last_used_at(
        cls,
        value: date | None,
        info: ValidationInfo,
    ) -> date | None:
        return validate_past_or_today_date(value, field_name=info.field_name or "last_used_at")


class UserSkillListParams(PageParams):
    """用户技能画像列表查询参数。"""

    statuses: list[UserSkillStatus] | None = Field(default=None, max_length=2)
    skill_ids: list[PositiveId] | None = Field(default=None, max_length=50)


class UserSkillResponse(BaseModel):
    """用户技能画像响应。"""

    id: int
    user_id: int
    skill_id: int
    status: UserSkillStatus
    source: UserSkillSource
    proficiency_level: UserSkillProficiencyLevel
    interest_level: UserSkillInterestLevel
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
