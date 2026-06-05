from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

from job_pilot.core.cache import CacheStore
from job_pilot.core.config import settings
from job_pilot.modules.auth.exceptions import InvalidCredentialsError
from job_pilot.modules.auth.utils.tokens import TokenData, decode_refresh_token

REFRESH_TOKEN_KEY_PREFIX = "auth:refresh:"


def _build_refresh_token_key(jwt_id: str) -> str:
    return f"{REFRESH_TOKEN_KEY_PREFIX}{jwt_id}"


def _hash_refresh_token(refresh_token: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        refresh_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _calculate_refresh_ttl_seconds(expires_at: datetime) -> int:
    return max(1, int((expires_at - datetime.now(UTC)).total_seconds()))


async def store_refresh_token(refresh_token: str, cache: CacheStore) -> TokenData:
    token_data = decode_refresh_token(refresh_token)
    await cache.set(
        _build_refresh_token_key(token_data.jti),
        _hash_refresh_token(refresh_token),
        ttl_seconds=_calculate_refresh_ttl_seconds(token_data.expires_at),
    )
    return token_data


async def consume_refresh_token(refresh_token: str, cache: CacheStore) -> TokenData:
    token_data = decode_refresh_token(refresh_token)
    key = _build_refresh_token_key(token_data.jti)
    stored_hash = await cache.take(key)
    if not isinstance(stored_hash, str):
        raise InvalidCredentialsError("Invalid refresh token")

    current_hash = _hash_refresh_token(refresh_token)
    if not hmac.compare_digest(stored_hash, current_hash):
        raise InvalidCredentialsError("Invalid refresh token")
    return token_data
