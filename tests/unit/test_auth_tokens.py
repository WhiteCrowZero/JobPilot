from __future__ import annotations

from datetime import timedelta

import pytest

from job_pilot.modules.auth.exceptions import (
    InvalidTokenError,
    InvalidTokenTypeError,
    TokenExpiredError,
)
from job_pilot.modules.auth.utils.tokens import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


def test_access_token_contains_user_identity() -> None:
    token = create_access_token(user_id=123)

    token_data = decode_access_token(token)

    assert token_data.user_id == 123
    assert token_data.sub == "123"
    assert token_data.jti
    assert token_data.token_type is TokenType.ACCESS


def test_access_token_cannot_be_used_as_refresh_token() -> None:
    access_token = create_access_token(user_id=123)

    with pytest.raises(InvalidTokenTypeError):
        decode_refresh_token(access_token)


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    refresh_token = create_refresh_token(user_id=123)

    with pytest.raises(InvalidTokenTypeError):
        decode_access_token(refresh_token)


def test_expired_token_is_rejected() -> None:
    token = create_access_token(user_id=123, expires_delta=timedelta(seconds=-1))

    with pytest.raises(TokenExpiredError):
        decode_access_token(token)


def test_invalid_token_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-jwt")
