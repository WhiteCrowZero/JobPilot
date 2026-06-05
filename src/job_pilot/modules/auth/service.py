from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.cache import CacheStore
from job_pilot.modules.auth import repository as auth_repository
from job_pilot.modules.auth.enums import AuthProvider
from job_pilot.modules.auth.exceptions import (
    AuthIdentityAlreadyExistsError,
    InvalidCredentialsError,
    UserInactiveError,
    WeakPasswordError,
)
from job_pilot.modules.auth.models import AuthIdentity
from job_pilot.modules.auth.schemas import (
    EmailRegisterRequest,
    PhoneRegisterRequest,
    TokenResponse,
)
from job_pilot.modules.auth.utils.email import normalize_email
from job_pilot.modules.auth.utils.password import (
    hash_password,
    validate_password_strong,
    verify_password,
)
from job_pilot.modules.auth.utils.phone import normalize_phone
from job_pilot.modules.auth.utils.refresh_store import (
    consume_refresh_token,
    store_refresh_token,
)
from job_pilot.modules.auth.utils.tokens import create_token_pair
from job_pilot.modules.users import repository as user_repository
from job_pilot.modules.users.enums import UserStatus
from job_pilot.modules.users.models import User
from job_pilot.modules.users.schemas import UserRead


async def register_with_email_password(
    payload: EmailRegisterRequest,
    session: AsyncSession,
    cache: CacheStore,
) -> TokenResponse:
    return await register_with_password_identity(
        provider=AuthProvider.EMAIL,
        provider_subject=normalize_email(str(payload.email)),
        display_name=payload.display_name,
        password=payload.password,
        session=session,
        cache=cache,
    )


async def register_with_phone_password(
    payload: PhoneRegisterRequest,
    session: AsyncSession,
    cache: CacheStore,
) -> TokenResponse:
    return await register_with_password_identity(
        provider=AuthProvider.PHONE,
        provider_subject=normalize_phone(payload.phone),
        display_name=payload.display_name,
        password=payload.password,
        session=session,
        cache=cache,
    )


async def register_with_password_identity(
    *,
    provider: AuthProvider,
    provider_subject: str,
    display_name: str,
    password: str,
    session: AsyncSession,
    cache: CacheStore,
) -> TokenResponse:
    try:
        validate_password_strong(password)
    except ValueError as exc:
        raise WeakPasswordError(str(exc)) from exc

    password_hash = hash_password(password)
    user: User | None = None

    try:
        async with session.begin():
            existing_identity = await auth_repository.get_password_identity(
                provider=provider,
                provider_subject=provider_subject,
                session=session,
            )
            if existing_identity is not None:
                raise AuthIdentityAlreadyExistsError.from_provider(provider)

            user = await user_repository.create_user(
                display_name=display_name,
                session=session,
                status=UserStatus.ACTIVE,
                is_superuser=False,
            )
            await auth_repository.create_password_identity(
                user=user,
                provider=provider,
                provider_subject=provider_subject,
                password_hash=password_hash,
                session=session,
            )
    except IntegrityError as exc:
        raise AuthIdentityAlreadyExistsError.from_provider(provider) from exc

    if user is None:
        raise InvalidCredentialsError("Registered user cannot be loaded")
    return await build_token_response(user, cache)


async def login_with_email_password(
    email: str,
    password: str,
    session: AsyncSession,
    cache: CacheStore,
) -> TokenResponse:
    return await login_with_password_identity(
        provider=AuthProvider.EMAIL,
        provider_subject=normalize_email(email),
        password=password,
        session=session,
        cache=cache,
    )


async def login_with_phone_password(
    phone: str,
    password: str,
    session: AsyncSession,
    cache: CacheStore,
) -> TokenResponse:
    return await login_with_password_identity(
        provider=AuthProvider.PHONE,
        provider_subject=normalize_phone(phone),
        password=password,
        session=session,
        cache=cache,
    )


async def login_with_password_identity(
    *,
    provider: AuthProvider,
    provider_subject: str,
    password: str,
    session: AsyncSession,
    cache: CacheStore,
) -> TokenResponse:
    user: User | None = None

    async with session.begin():
        identity = await authenticate_identity(
            provider=provider,
            provider_subject=provider_subject,
            password=password,
            session=session,
        )
        if identity is None:
            raise InvalidCredentialsError()
        if not identity.user.is_active:
            raise UserInactiveError()

        user = await user_repository.update_last_login_at(identity.user, session)
        await auth_repository.update_identity_last_login_at(identity, session)

    if user is None:
        raise InvalidCredentialsError("Authenticated user cannot be loaded")
    return await build_token_response(user, cache)


async def refresh_login(
    refresh_token: str,
    session: AsyncSession,
    cache: CacheStore,
) -> TokenResponse:
    token_data = await consume_refresh_token(refresh_token, cache)
    user = await user_repository.get_user_by_id(token_data.user_id, session)
    if user is None:
        raise InvalidCredentialsError("Invalid refresh token")
    if not user.is_active:
        raise UserInactiveError()

    return await build_token_response(user, cache)


async def authenticate_identity(
    *,
    provider: AuthProvider,
    provider_subject: str,
    password: str,
    session: AsyncSession,
) -> AuthIdentity | None:
    identity = await auth_repository.get_password_identity(
        provider=provider,
        provider_subject=provider_subject,
        session=session,
    )
    if identity is None or identity.password_credential is None:
        return None
    if not verify_password(password, identity.password_credential.password_hash):
        return None
    return identity


async def authenticate_user_by_email(
    email: str,
    password: str,
    session: AsyncSession,
) -> User | None:
    identity = await authenticate_identity(
        provider=AuthProvider.EMAIL,
        provider_subject=normalize_email(email),
        password=password,
        session=session,
    )
    if identity is None:
        return None
    return identity.user


async def authenticate_user_by_phone(
    phone: str,
    password: str,
    session: AsyncSession,
) -> User | None:
    identity = await authenticate_identity(
        provider=AuthProvider.PHONE,
        provider_subject=normalize_phone(phone),
        password=password,
        session=session,
    )
    if identity is None:
        return None
    return identity.user


async def build_token_response(user: User, cache: CacheStore) -> TokenResponse:
    access_token, refresh_token = create_token_pair(user.id)
    await store_refresh_token(refresh_token, cache)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )


async def logout_by_token(refresh_token: str, cache: CacheStore) -> None:
    await consume_refresh_token(refresh_token, cache)
