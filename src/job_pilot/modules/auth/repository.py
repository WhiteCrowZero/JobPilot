from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_pilot.modules.auth.enums import AuthProviderType
from job_pilot.modules.auth.models import AuthAccount
from job_pilot.modules.users.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_auth_account_by_email(
    email: str,
    session: AsyncSession,
) -> AuthAccount | None:
    result = await session.execute(
        select(AuthAccount)
        .options(selectinload(AuthAccount.user))
        .where(
            AuthAccount.provider_type == AuthProviderType.EMAIL,
            AuthAccount.provider_account == normalize_email(email),
        )
    )
    return result.scalar_one_or_none()


async def create_email_auth_account(
    *,
    user: User,
    email: str,
    password_hash: str,
    session: AsyncSession,
    is_primary: bool = True,
    is_verified: bool = False,
) -> AuthAccount:
    auth_account = AuthAccount(
        user=user,
        provider_type=AuthProviderType.EMAIL,
        provider_account=normalize_email(email),
        password_hash=password_hash,
        is_primary=is_primary,
        is_verified=is_verified,
    )
    session.add(auth_account)
    await session.flush()
    return auth_account
