from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.cache import CacheStore
from job_pilot.core.logging import log_app_event
from job_pilot.modules.auth.contracts import EmailRegisterCommand, PhoneRegisterCommand
from job_pilot.modules.auth.enums import AuthProvider
from job_pilot.modules.auth.exceptions import (
    AuthIdentityAlreadyExistsError,
    InvalidCredentialsError,
    UserInactiveError,
    WeakPasswordError,
)
from job_pilot.modules.auth.models import AuthIdentity
from job_pilot.modules.auth.repository import AuthRepository, build_auth_repository
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
from job_pilot.modules.users.enums import UserStatus
from job_pilot.modules.users.models import User
from job_pilot.modules.users.service import UserService, build_user_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthTokenSnapshot:
    """认证成功后的轻量 token 快照。"""

    access_token: str
    refresh_token: str
    token_type: str
    user: User


class AuthService:
    """认证 service，负责注册、登录、刷新和退出登录。"""

    def __init__(self, repository: AuthRepository, user_service: UserService) -> None:
        self.repository: AuthRepository = repository
        self.user_service: UserService = user_service

    async def register_with_email_password(
        self,
        db: AsyncSession,
        *,
        payload: EmailRegisterCommand,
        cache: CacheStore,
    ) -> AuthTokenSnapshot:
        """使用邮箱和密码注册。"""

        return await self._register_with_password_identity(
            db,
            provider=AuthProvider.EMAIL,
            provider_subject=normalize_email(str(payload.email)),
            display_name=payload.display_name,
            password=payload.password,
            cache=cache,
        )

    async def register_with_phone_password(
        self,
        db: AsyncSession,
        *,
        payload: PhoneRegisterCommand,
        cache: CacheStore,
    ) -> AuthTokenSnapshot:
        """使用手机号和密码注册。"""

        return await self._register_with_password_identity(
            db,
            provider=AuthProvider.PHONE,
            provider_subject=normalize_phone(payload.phone),
            display_name=payload.display_name,
            password=payload.password,
            cache=cache,
        )

    async def _register_with_password_identity(
        self,
        db: AsyncSession,
        *,
        provider: AuthProvider,
        provider_subject: str,
        display_name: str,
        password: str,
        cache: CacheStore,
    ) -> AuthTokenSnapshot:
        """创建用户、登录身份和密码凭证。"""

        try:
            validate_password_strong(password)
        except ValueError as exc:
            raise WeakPasswordError(str(exc)) from exc

        password_hash = hash_password(password)
        user: User | None = None

        try:
            existing_identity = await self.repository.get_password_identity(
                db,
                provider=provider,
                provider_subject=provider_subject,
            )
            if existing_identity is not None:
                log_app_event(
                    logger,
                    "Registration rejected because identity already exists",
                    extra={"auth_provider": provider.value},
                )
                raise AuthIdentityAlreadyExistsError.from_provider(provider)

            user = await self.user_service.create_user(
                db,
                display_name=display_name,
                status=UserStatus.ACTIVE,
                is_superuser=False,
            )

            if user is None:
                raise InvalidCredentialsError("Registered user cannot be loaded")

            await self.repository.create_password_identity(
                db,
                user=user,
                provider=provider,
                provider_subject=provider_subject,
                password_hash=password_hash,
            )
        except IntegrityError as exc:
            log_app_event(
                logger,
                "Registration rejected by database unique constraint",
                extra={"auth_provider": provider.value},
            )
            raise AuthIdentityAlreadyExistsError.from_provider(provider) from exc

        if user is None:
            raise InvalidCredentialsError("Registered user cannot be loaded")
        return await self._build_token_snapshot(user=user, cache=cache)

    async def login_with_email_password(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str,
        cache: CacheStore,
    ) -> AuthTokenSnapshot:
        """使用邮箱和密码登录。"""

        return await self._login_with_password_identity(
            db,
            provider=AuthProvider.EMAIL,
            provider_subject=normalize_email(email),
            password=password,
            cache=cache,
        )

    async def login_with_phone_password(
        self,
        db: AsyncSession,
        *,
        phone: str,
        password: str,
        cache: CacheStore,
    ) -> AuthTokenSnapshot:
        """使用手机号和密码登录。"""

        return await self._login_with_password_identity(
            db,
            provider=AuthProvider.PHONE,
            provider_subject=normalize_phone(phone),
            password=password,
            cache=cache,
        )

    async def _login_with_password_identity(
        self,
        db: AsyncSession,
        *,
        provider: AuthProvider,
        provider_subject: str,
        password: str,
        cache: CacheStore,
    ) -> AuthTokenSnapshot:
        """校验密码登录身份并更新登录时间。"""

        user: User | None = None

        identity = await self.authenticate_identity(
            db,
            provider=provider,
            provider_subject=provider_subject,
            password=password,
        )
        if identity is None:
            log_app_event(
                logger,
                "Password login failed",
                extra={"auth_provider": provider.value},
            )
            raise InvalidCredentialsError()
        if not identity.user.is_active:
            log_app_event(
                logger,
                "Inactive user login rejected",
                extra={"auth_provider": provider.value, "user_id": identity.user.id},
            )
            raise UserInactiveError()

        if identity.user is None:
            raise InvalidCredentialsError("Authenticated user cannot be loaded")

        user = await self.user_service.update_last_login_at(db, user=identity.user)
        await self.repository.update_identity_last_login_at(db, identity=identity)

        if user is None:
            raise InvalidCredentialsError("Authenticated user cannot be loaded")
        return await self._build_token_snapshot(user=user, cache=cache)

    async def refresh_login(
        self,
        db: AsyncSession,
        *,
        refresh_token: str,
        cache: CacheStore,
    ) -> AuthTokenSnapshot:
        """消费 refresh token 并签发新的 token 对。"""

        token_data = await consume_refresh_token(refresh_token, cache)
        user = await self.user_service.get_user_by_id(db, user_id=token_data.user_id)
        if user is None:
            log_app_event(logger, "Refresh token rejected because user was not found")
            raise InvalidCredentialsError("Invalid refresh token")
        if not user.is_active:
            log_app_event(
                logger,
                "Refresh token rejected for inactive user",
                extra={"user_id": user.id},
            )
            raise UserInactiveError()

        return await self._build_token_snapshot(user=user, cache=cache)

    async def authenticate_identity(
        self,
        db: AsyncSession,
        *,
        provider: AuthProvider,
        provider_subject: str,
        password: str,
    ) -> AuthIdentity | None:
        """校验密码登录身份。"""

        identity = await self.repository.get_password_identity(
            db,
            provider=provider,
            provider_subject=provider_subject,
        )
        if identity is None or identity.password_credential is None:
            return None
        if not verify_password(password, identity.password_credential.password_hash):
            return None
        return identity

    async def authenticate_user_by_email(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str,
    ) -> User | None:
        """使用邮箱密码认证用户。"""

        identity = await self.authenticate_identity(
            db,
            provider=AuthProvider.EMAIL,
            provider_subject=normalize_email(email),
            password=password,
        )
        if identity is None:
            return None
        return identity.user

    async def authenticate_user_by_phone(
        self,
        db: AsyncSession,
        *,
        phone: str,
        password: str,
    ) -> User | None:
        """使用手机号密码认证用户。"""

        identity = await self.authenticate_identity(
            db,
            provider=AuthProvider.PHONE,
            provider_subject=normalize_phone(phone),
            password=password,
        )
        if identity is None:
            return None
        return identity.user

    async def logout_by_token(self, *, refresh_token: str, cache: CacheStore) -> None:
        """消费 refresh token，实现退出登录。"""

        await consume_refresh_token(refresh_token, cache)

    async def _build_token_snapshot(self, *, user: User, cache: CacheStore) -> AuthTokenSnapshot:
        """生成 token 快照并写入 refresh token 存储。"""

        access_token, refresh_token = create_token_pair(user.id)
        await store_refresh_token(refresh_token, cache)
        return AuthTokenSnapshot(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=user,
        )


def build_auth_service() -> AuthService:
    """构建认证 service。"""

    return AuthService(
        repository=build_auth_repository(),
        user_service=build_user_service(),
    )
