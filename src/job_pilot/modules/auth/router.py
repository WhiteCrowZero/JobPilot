from __future__ import annotations

from fastapi import APIRouter
from starlette import status

from job_pilot.api.deps import CurrentCacheStoreDep, DbSessionDep
from job_pilot.modules.auth.schemas import (
    EmailLoginRequest,
    EmailRegisterRequest,
    LogoutRequest,
    LogoutResponse,
    PhoneLoginRequest,
    PhoneRegisterRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from job_pilot.modules.auth.service import (
    login_with_email_password,
    login_with_phone_password,
    logout_by_token,
    refresh_login,
    register_with_email_password,
    register_with_phone_password,
)

router = APIRouter()


@router.post("/register/email", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_with_email(
    payload: EmailRegisterRequest,
    session: DbSessionDep,
    cache: CurrentCacheStoreDep,
) -> TokenResponse:
    return await register_with_email_password(payload, session, cache)


@router.post("/register/phone", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_with_phone(
    payload: PhoneRegisterRequest,
    session: DbSessionDep,
    cache: CurrentCacheStoreDep,
) -> TokenResponse:
    return await register_with_phone_password(payload, session, cache)


@router.post("/login/email", response_model=TokenResponse)
async def login_with_email(
    payload: EmailLoginRequest,
    session: DbSessionDep,
    cache: CurrentCacheStoreDep,
) -> TokenResponse:
    return await login_with_email_password(payload.email, payload.password, session, cache)


@router.post("/login/phone", response_model=TokenResponse)
async def login_with_phone(
    payload: PhoneLoginRequest,
    session: DbSessionDep,
    cache: CurrentCacheStoreDep,
) -> TokenResponse:
    return await login_with_phone_password(payload.phone, payload.password, session, cache)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshTokenRequest,
    session: DbSessionDep,
    cache: CurrentCacheStoreDep,
) -> TokenResponse:
    return await refresh_login(payload.refresh_token, session, cache)


@router.post("/logout", response_model=LogoutResponse)
async def logout(payload: LogoutRequest, cache: CurrentCacheStoreDep) -> LogoutResponse:
    await logout_by_token(payload.refresh_token, cache)
    return LogoutResponse()
