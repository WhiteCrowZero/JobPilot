from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot, build_job_pilot
from job_pilot.core.cache import CacheStore, DistributedLock
from job_pilot.core.exceptions import ForbiddenError, UnauthorizedError
from job_pilot.core.resources import AppResources
from job_pilot.modules.auth.exceptions import TokenError
from job_pilot.modules.auth.utils.tokens import decode_access_token
from job_pilot.modules.users.models import User
from job_pilot.modules.users.service import build_user_service


def get_resources(request: Request) -> AppResources:
    return request.app.state.resources


def get_job_pilot(request: Request) -> JobPilot:
    """构建当前请求使用的公开业务入口。"""

    return build_job_pilot(get_resources(request))


JobPilotDep = Annotated[JobPilot, Depends(get_job_pilot)]


bearer_scheme = HTTPBearer(auto_error=False)
user_service = build_user_service()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources = get_resources(request)
    async with resources.require_database().session_factory() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Could not validate credentials", code="INVALID_CREDENTIALS")
    return credentials.credentials


TokenDep = Annotated[str, Depends(get_bearer_token)]


async def get_current_user(token: TokenDep, session: DbSessionDep) -> User:
    try:
        token_data = decode_access_token(token)
    except TokenError as exc:
        raise UnauthorizedError(exc.message, code=exc.code) from exc

    user = await user_service.get_user_by_id(session, user_id=token_data.user_id)
    if user is None:
        raise UnauthorizedError("Could not validate credentials", code="INVALID_CREDENTIALS")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise ForbiddenError("Account is disabled", code="ACCOUNT_DISABLED")
    return current_user


CurrentActiveUserDep = Annotated[User, Depends(get_current_active_user)]


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    if not current_user.is_superuser:
        raise ForbiddenError("Not enough permissions", code="NOT_ENOUGH_PERMISSIONS")
    return current_user


CurrentSuperuserDep = Annotated[User, Depends(get_current_superuser)]


def get_cache_store(request: Request) -> CacheStore:
    return get_resources(request).require_cache()


CurrentCacheStoreDep = Annotated[CacheStore, Depends(get_cache_store)]


def get_distributed_lock(request: Request) -> DistributedLock:
    return get_resources(request).require_lock()


CurrentDistributedLockDep = Annotated[DistributedLock, Depends(get_distributed_lock)]
