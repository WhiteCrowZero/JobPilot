from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.users import repository as user_repository
from job_pilot.modules.users.models import User


async def get_user_or_none(user_id: int, session: AsyncSession) -> User | None:
    return await user_repository.get_user_by_id(user_id, session)
