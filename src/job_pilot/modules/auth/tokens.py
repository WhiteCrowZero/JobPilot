from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from pydantic import BaseModel

from job_pilot.core.config import settings
from job_pilot.modules.auth.exceptions import (
    InvalidTokenError,
    InvalidTokenTypeError,
    TokenExpiredError,
)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenData(BaseModel):
    user_id: int
    sub: str
    token_type: TokenType
    expires_at: datetime


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    expires_in = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(user_id=user_id, token_type=TokenType.ACCESS, expires_delta=expires_in)


def create_refresh_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    expires_in = expires_delta or timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    return _create_token(user_id=user_id, token_type=TokenType.REFRESH, expires_delta=expires_in)


def create_token_pair(user_id: int) -> tuple[str, str]:
    return create_access_token(user_id), create_refresh_token(user_id)


def decode_token(token: str, expected_type: TokenType | None = None) -> TokenData:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid token") from exc

    token_data = _parse_payload(payload)
    if expected_type is not None and token_data.token_type != expected_type:
        raise InvalidTokenTypeError("Invalid token type")
    return token_data


def decode_access_token(token: str) -> TokenData:
    return decode_token(token, expected_type=TokenType.ACCESS)


def decode_refresh_token(token: str) -> TokenData:
    return decode_token(token, expected_type=TokenType.REFRESH)


def refresh_access_token(refresh_token: str) -> str:
    token_data = decode_refresh_token(refresh_token)
    return create_access_token(token_data.user_id)


def decode_token_payload(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid token") from exc


def _create_token(*, user_id: int, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    expire = now + expires_delta
    subject = str(user_id)
    payload: dict[str, Any] = {
        "sub": subject,
        "user_id": user_id,
        "token_type": token_type.value,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _parse_payload(payload: dict[str, Any]) -> TokenData:
    subject = payload.get("sub")
    token_type_value = payload.get("token_type")
    expires_at_value = payload.get("exp")

    if not isinstance(subject, str) or not subject:
        raise InvalidTokenError("Token subject is missing")
    if not isinstance(token_type_value, str):
        raise InvalidTokenError("Token type is missing")

    try:
        user_id = int(payload.get("user_id", subject))
        token_type = TokenType(token_type_value)
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("Token payload is invalid") from exc

    if str(user_id) != subject:
        raise InvalidTokenError("Token subject does not match user id")

    if not isinstance(expires_at_value, int | float):
        raise InvalidTokenError("Token expiration is missing")

    return TokenData(
        user_id=user_id,
        sub=subject,
        token_type=token_type,
        expires_at=datetime.fromtimestamp(expires_at_value, UTC),
    )
