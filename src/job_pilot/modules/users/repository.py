from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.users.enums import UserStatus
from job_pilot.modules.users.models import User


async def get_user_by_id(user_id: int, session: AsyncSession) -> User | None:
    return await session.get(User, user_id)


async def create_user(
    *,
    display_name: str,
    session: AsyncSession,
    status: UserStatus = UserStatus.ACTIVE,
    is_superuser: bool = False,
) -> User:
    user = User(
        display_name=display_name,
        status=status,
        is_superuser=is_superuser,
    )
    session.add(user)
    await session.flush()
    return user


async def update_last_login_at(user: User, session: AsyncSession) -> User:
    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user
