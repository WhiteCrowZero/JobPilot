from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_pilot.modules.auth.enums import AuthProvider
from job_pilot.modules.auth.models import AuthIdentity, AuthPasswordCredential
from job_pilot.modules.users.models import User


class AuthRepository:
    """认证仓储，封装登录身份和密码凭证的数据库操作。"""

    async def get_password_identity(
        self,
        db: AsyncSession,
        *,
        provider: AuthProvider,
        provider_subject: str,
    ) -> AuthIdentity | None:
        """读取密码登录身份，并预加载用户和密码凭证。"""

        result = await db.execute(
            select(AuthIdentity)
            .options(
                selectinload(AuthIdentity.user).selectinload(User.profile),
                selectinload(AuthIdentity.password_credential),
            )
            .where(
                AuthIdentity.provider == provider,
                AuthIdentity.provider_subject == provider_subject,
            )
        )
        return result.scalar_one_or_none()

    async def create_password_identity(
        self,
        db: AsyncSession,
        *,
        user: User,
        provider: AuthProvider,
        provider_subject: str,
        password_hash: str,
    ) -> AuthIdentity:
        """创建密码登录身份和密码凭证。"""

        identity = AuthIdentity(
            user=user,
            provider=provider,
            provider_subject=provider_subject,
            provider_email=provider_subject if provider == AuthProvider.EMAIL else None,
            provider_phone=provider_subject if provider == AuthProvider.PHONE else None,
            password_credential=AuthPasswordCredential(password_hash=password_hash),
        )
        db.add(identity)
        await db.flush()
        return identity

    async def update_identity_last_login_at(
        self,
        db: AsyncSession,
        *,
        identity: AuthIdentity,
    ) -> AuthIdentity:
        """更新登录身份最近登录时间。"""

        identity.last_login_at = datetime.now(UTC)
        await db.flush()
        return identity


def build_auth_repository() -> AuthRepository:
    """构建认证仓储。"""

    return AuthRepository()
