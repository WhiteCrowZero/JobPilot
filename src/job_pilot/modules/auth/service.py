from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.auth import repository as auth_repository
from job_pilot.modules.auth.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserInactiveError,
    WeakPasswordError,
)
from job_pilot.modules.auth.password import (
    hash_password,
    validate_password_strong,
    verify_password,
)
from job_pilot.modules.auth.schemas import RegisterRequest, TokenResponse
from job_pilot.modules.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from job_pilot.modules.users import repository as user_repository
from job_pilot.modules.users.enums import UserStatus
from job_pilot.modules.users.models import User
from job_pilot.modules.users.schemas import UserRead


async def register_with_password(payload: RegisterRequest, session: AsyncSession) -> TokenResponse:
    existing_account = await auth_repository.get_auth_account_by_email(payload.email, session)
    if existing_account is not None:
        raise UserAlreadyExistsError("Email is already registered")

    try:
        validate_password_strong(payload.password)
    except ValueError as exc:
        raise WeakPasswordError(str(exc)) from exc

    try:
        user = await user_repository.create_user(
            display_name=payload.display_name,
            session=session,
            status=UserStatus.ACTIVE,
            is_superuser=False,
        )
        await auth_repository.create_email_auth_account(
            user=user,
            email=payload.email,
            password_hash=hash_password(payload.password),
            session=session,
            is_verified=False,
        )
        await session.commit()
        await session.refresh(user)
    except Exception:
        await session.rollback()
        raise

    return build_token_response(user)


async def login_with_password(
    email: str,
    password: str,
    session: AsyncSession,
) -> TokenResponse:
    user = await authenticate_user_by_email(email, password, session)
    if user is None:
        raise InvalidCredentialsError("Invalid email or password")
    if not user.is_active:
        raise UserInactiveError("Account is disabled")

    try:
        user = await user_repository.update_last_login_at(user, session)
        await session.commit()
        await session.refresh(user)
    except Exception:
        await session.rollback()
        raise

    return build_token_response(user)


async def refresh_login(refresh_token: str, session: AsyncSession) -> TokenResponse:
    token_data = decode_refresh_token(refresh_token)
    user = await user_repository.get_user_by_id(token_data.user_id, session)
    if user is None:
        raise InvalidCredentialsError("Invalid refresh token")
    if not user.is_active:
        raise UserInactiveError("Account is disabled")

    return build_token_response(user, refresh_token=refresh_token)


async def authenticate_user_by_email(
    email: str,
    password: str,
    session: AsyncSession,
) -> User | None:
    account = await auth_repository.get_auth_account_by_email(email, session)
    if account is None or account.password_hash is None:
        return None
    if not verify_password(password, account.password_hash):
        return None
    return account.user


def build_token_response(user: User, refresh_token: str | None = None) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token or create_refresh_token(user.id),
        token_type="bearer",
        user=UserRead.model_validate(user),
    )
