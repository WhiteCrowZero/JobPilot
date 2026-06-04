from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from job_pilot.core.cache import CacheStore, DistributedLock
from job_pilot.core.exceptions import ForbiddenError
from job_pilot.core.message_queue import MessageQueue
from job_pilot.core.resources import AppResources
from job_pilot.modules.auth.exceptions import TokenError
from job_pilot.modules.auth.tokens import decode_access_token
from job_pilot.modules.users import repository as user_repository
from job_pilot.modules.users.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources = get_resources(request)
    async with resources.database.session_factory() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(token: TokenDep, session: DbSessionDep) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token_data = decode_access_token(token)
    except TokenError:
        raise credentials_exception from None

    user = await user_repository.get_user_by_id(token_data.user_id, session)
    if user is None:
        raise credentials_exception
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise ForbiddenError("Account is disabled")
    return current_user


CurrentActiveUserDep = Annotated[User, Depends(get_current_active_user)]


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    if not current_user.is_superuser:
        raise ForbiddenError("Not enough permissions")
    return current_user


CurrentSuperuserDep = Annotated[User, Depends(get_current_superuser)]


def get_resources(request: Request) -> AppResources:
    return request.app.state.resources


def get_cache_store(request: Request) -> CacheStore:
    return get_resources(request).cache


def get_distributed_lock(request: Request) -> DistributedLock:
    return get_resources(request).lock
