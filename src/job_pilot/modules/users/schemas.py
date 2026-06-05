from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from job_pilot.modules.users.enums import UserStatus


class UserProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=300)


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    display_name: str
    avatar_url: str | None
    bio: str | None
    created_at: datetime
    updated_at: datetime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: UserStatus
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    profile: UserProfileRead | None
