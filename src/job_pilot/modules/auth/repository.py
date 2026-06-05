from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_pilot.modules.auth.enums import AuthProvider
from job_pilot.modules.auth.models import AuthIdentity, AuthPasswordCredential
from job_pilot.modules.users.models import User


async def get_password_identity(
    *,
    provider: AuthProvider,
    provider_subject: str,
    session: AsyncSession,
) -> AuthIdentity | None:
    result = await session.execute(
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
    *,
    user: User,
    provider: AuthProvider,
    provider_subject: str,
    password_hash: str,
    session: AsyncSession,
) -> AuthIdentity:
    identity = AuthIdentity(
        user=user,
        provider=provider,
        provider_subject=provider_subject,
        provider_email=provider_subject if provider == AuthProvider.EMAIL else None,
        provider_phone=provider_subject if provider == AuthProvider.PHONE else None,
        password_credential=AuthPasswordCredential(password_hash=password_hash),
    )
    session.add(identity)
    await session.flush()
    return identity


async def update_identity_last_login_at(
    identity: AuthIdentity,
    session: AsyncSession,
) -> AuthIdentity:
    identity.last_login_at = datetime.now(UTC)
    await session.flush()
    return identity
