from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette import status

from job_pilot.api.deps import DbSessionDep
from job_pilot.modules.auth.exceptions import (
    AuthError,
    InvalidCredentialsError,
    TokenError,
    UserAlreadyExistsError,
    UserInactiveError,
    WeakPasswordError,
)
from job_pilot.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from job_pilot.modules.auth.service import (
    login_with_password,
    refresh_login,
    register_with_password,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: DbSessionDep) -> TokenResponse:
    try:
        return await register_with_password(payload, session)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeakPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: DbSessionDep) -> TokenResponse:
    try:
        return await login_with_password(payload.email, payload.password, session)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except UserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        ) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshTokenRequest, session: DbSessionDep) -> TokenResponse:
    try:
        return await refresh_login(payload.refresh_token, session)
    except (InvalidCredentialsError, TokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except UserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        ) from exc
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
