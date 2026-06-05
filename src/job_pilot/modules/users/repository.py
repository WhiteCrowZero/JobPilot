from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_pilot.modules.users.enums import UserStatus
from job_pilot.modules.users.models import User, UserProfile


async def get_user_by_id(user_id: int, session: AsyncSession) -> User | None:
    result = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    *,
    display_name: str,
    session: AsyncSession,
    avatar_url: str | None = None,
    status: UserStatus = UserStatus.ACTIVE,
    is_superuser: bool = False,
) -> User:
    user = User(
        status=status,
        is_superuser=is_superuser,
        profile=UserProfile(
            display_name=display_name,
            avatar_url=avatar_url,
        ),
    )
    session.add(user)
    await session.flush()
    return user


async def update_last_login_at(user: User, session: AsyncSession) -> User:
    user.last_login_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(
        user,
        attribute_names=["last_login_at", "updated_at"],
    )
    return user
