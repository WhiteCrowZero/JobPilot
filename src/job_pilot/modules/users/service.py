from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.users.enums import UserStatus
from job_pilot.modules.users.models import User
from job_pilot.modules.users.repository import UserRepository, build_user_repository


class UserService:
    """用户 service，承载用户主体的领域操作。"""

    def __init__(self, repository: UserRepository) -> None:
        self.repository: UserRepository = repository

    async def get_user_by_id(self, db: AsyncSession, *, user_id: int) -> User | None:
        """按主键读取用户。"""

        return await self.repository.get_user_by_id(db, user_id=user_id)

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

        return await self.repository.create_user(
            db,
            display_name=display_name,
            avatar_url=avatar_url,
            status=status,
            is_superuser=is_superuser,
        )

    async def update_last_login_at(self, db: AsyncSession, *, user: User) -> User:
        """更新用户最近登录时间。"""

        return await self.repository.update_last_login_at(db, user=user)


def build_user_service() -> UserService:
    """构建用户 service。"""

    return UserService(repository=build_user_repository())
