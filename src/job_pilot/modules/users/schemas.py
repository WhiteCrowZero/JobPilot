from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from job_pilot.modules.users.enums import UserStatus


class UserBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=50)
    status: UserStatus = UserStatus.ACTIVE


class UserCreate(UserBase):
    is_superuser: bool = False


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    status: UserStatus
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
