from __future__ import annotations

from fastapi import APIRouter
from starlette import status

from job_pilot.api.deps import JobPilotDep
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
from job_pilot.modules.auth.service import AuthTokenSnapshot
from job_pilot.modules.users.schemas import UserRead

router = APIRouter()


@router.post("/register/email", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_with_email(
    payload: EmailRegisterRequest,
    pilot: JobPilotDep,
) -> TokenResponse:
    token_snapshot = await pilot.auth.register_with_email(payload)
    return _to_token_response(token_snapshot)


@router.post("/register/phone", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_with_phone(
    payload: PhoneRegisterRequest,
    pilot: JobPilotDep,
) -> TokenResponse:
    token_snapshot = await pilot.auth.register_with_phone(payload)
    return _to_token_response(token_snapshot)


@router.post("/login/email", response_model=TokenResponse)
async def login_with_email(
    payload: EmailLoginRequest,
    pilot: JobPilotDep,
) -> TokenResponse:
    token_snapshot = await pilot.auth.login_with_email(
        email=payload.email, password=payload.password
    )
    return _to_token_response(token_snapshot)


@router.post("/login/phone", response_model=TokenResponse)
async def login_with_phone(
    payload: PhoneLoginRequest,
    pilot: JobPilotDep,
) -> TokenResponse:
    token_snapshot = await pilot.auth.login_with_phone(
        phone=payload.phone, password=payload.password
    )
    return _to_token_response(token_snapshot)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshTokenRequest,
    pilot: JobPilotDep,
) -> TokenResponse:
    token_snapshot = await pilot.auth.refresh_login(refresh_token=payload.refresh_token)
    return _to_token_response(token_snapshot)


@router.post("/logout", response_model=LogoutResponse)
async def logout(payload: LogoutRequest, pilot: JobPilotDep) -> LogoutResponse:
    await pilot.auth.logout(refresh_token=payload.refresh_token)
    return LogoutResponse()


def _to_token_response(token_snapshot: AuthTokenSnapshot) -> TokenResponse:
    """将 service 快照转换为 API 响应模型。"""

    return TokenResponse(
        access_token=token_snapshot.access_token,
        refresh_token=token_snapshot.refresh_token,
        token_type=token_snapshot.token_type,
        user=UserRead.model_validate(token_snapshot.user),
    )
