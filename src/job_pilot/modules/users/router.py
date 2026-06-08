from __future__ import annotations

from fastapi import APIRouter

from job_pilot.api.deps import CurrentActiveUserDep
from job_pilot.modules.users.schemas import UserRead

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: CurrentActiveUserDep) -> UserRead:
    return UserRead.model_validate(current_user)
