from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_pilot.modules.users.enums import UserStatus
from job_pilot.modules.users.models import User, UserProfile


class UserRepository:
    """用户仓储，封装用户主体和资料的数据库操作。"""

    async def get_user_by_id(self, db: AsyncSession, *, user_id: int) -> User | None:
        """按主键读取用户，并预加载 profile。"""

        result = await db.execute(
            select(User).options(selectinload(User.profile)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        db: AsyncSession,
        *,
        display_name: str,
        avatar_url: str | None = None,
        status: UserStatus = UserStatus.ACTIVE,
        is_superuser: bool = False,
    ) -> User:
        """创建用户主体和用户资料。"""

        user = User(
            status=status,
            is_superuser=is_superuser,
            profile=UserProfile(
                display_name=display_name,
                avatar_url=avatar_url,
            ),
        )
        db.add(user)
        await db.flush()
        return user

    async def update_last_login_at(self, db: AsyncSession, *, user: User) -> User:
        """更新用户最近登录时间。"""

        user.last_login_at = datetime.now(UTC)
        await db.flush()
        await db.refresh(
            user,
            attribute_names=["last_login_at", "updated_at"],
        )
        return user


def build_user_repository() -> UserRepository:
    """构建用户仓储。"""

    return UserRepository()
