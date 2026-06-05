from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.cache import CacheValue
from job_pilot.modules.auth.enums import AuthProvider
from job_pilot.modules.auth.exceptions import InvalidCredentialsError
from job_pilot.modules.auth.models import AuthIdentity, AuthPasswordCredential
from job_pilot.modules.auth.schemas import EmailRegisterRequest, PhoneRegisterRequest
from job_pilot.modules.auth.service import (
    login_with_email_password,
    login_with_phone_password,
    logout_by_token,
    refresh_login,
    register_with_email_password,
    register_with_phone_password,
)
from job_pilot.modules.auth.utils.tokens import decode_access_token, decode_refresh_token


class MemoryCacheStore:
    def __init__(self) -> None:
        self.items: dict[str, CacheValue] = {}
        self.get_calls = 0
        self.take_calls = 0

    async def get(self, key: str) -> CacheValue | None:
        self.get_calls += 1
        return self.items.get(key)

    async def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        _ = ttl_seconds
        self.items[key] = value

    async def take(self, key: str) -> CacheValue | None:
        self.take_calls += 1
        return self.items.pop(key, None)

    async def delete(self, key: str) -> None:
        self.items.pop(key, None)

    async def delete_by_prefix(self, prefix: str) -> int:
        keys = [key for key in self.items if key.startswith(prefix)]
        for key in keys:
            self.items.pop(key, None)
        return len(keys)

    async def close(self) -> None:
        self.items.clear()


@pytest.fixture
def cache_store() -> MemoryCacheStore:
    return MemoryCacheStore()


@pytest.fixture(autouse=True)
def use_fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_hash_password(password: str) -> str:
        return f"test-hash:{password}"

    def fake_verify_password(plain_password: str, hashed_password: str) -> bool:
        return hashed_password == fake_hash_password(plain_password)

    monkeypatch.setattr("job_pilot.modules.auth.service.hash_password", fake_hash_password)
    monkeypatch.setattr("job_pilot.modules.auth.service.verify_password", fake_verify_password)


@pytest.mark.asyncio
async def test_register_with_email_password_creates_identity_credential_and_profile(
    db_session: AsyncSession,
    cache_store: MemoryCacheStore,
) -> None:
    # Arrange
    email = f"service-register-{uuid4().hex}@example.com"
    request = EmailRegisterRequest(
        email=email,
        password="Password123",
        display_name="Service User",
    )

    # Act
    response = await register_with_email_password(request, db_session, cache_store)

    # Assert
    assert response.user.profile is not None
    assert response.user.profile.display_name == "Service User"

    identity_result = await db_session.execute(select(AuthIdentity))
    identity = identity_result.scalar_one()
    assert identity.provider == AuthProvider.EMAIL
    assert identity.provider_subject == email
    assert identity.provider_email == email
    assert identity.provider_phone is None

    credential_result = await db_session.execute(select(AuthPasswordCredential))
    credential = credential_result.scalar_one()
    assert credential.identity_id == identity.id
    assert credential.password_hash != "Password123"


@pytest.mark.asyncio
async def test_register_with_phone_password_creates_phone_identity(
    db_session: AsyncSession,
    cache_store: MemoryCacheStore,
) -> None:
    # Arrange
    phone = f"+1202{uuid4().int % 10_000_000:07d}"
    request = PhoneRegisterRequest(
        phone=phone,
        password="Password123",
        display_name="Phone User",
    )

    # Act
    response = await register_with_phone_password(request, db_session, cache_store)

    # Assert
    assert response.user.profile is not None
    assert response.user.profile.display_name == "Phone User"

    identity_result = await db_session.execute(select(AuthIdentity))
    identity = identity_result.scalar_one()
    assert identity.provider == AuthProvider.PHONE
    assert identity.provider_subject == phone
    assert identity.provider_phone == phone
    assert identity.provider_email is None


@pytest.mark.asyncio
async def test_login_with_password_updates_login_times(
    db_session: AsyncSession,
    cache_store: MemoryCacheStore,
) -> None:
    # Arrange
    email = f"service-login-{uuid4().hex}@example.com"
    password = "Password123"
    await register_with_email_password(
        EmailRegisterRequest(email=email, password=password, display_name="Login User"),
        db_session,
        cache_store,
    )

    # Act
    response = await login_with_email_password(email, password, db_session, cache_store)

    # Assert
    assert response.user.last_login_at is not None

    identity_result = await db_session.execute(select(AuthIdentity))
    identity = identity_result.scalar_one()
    assert identity.last_login_at is not None


@pytest.mark.asyncio
async def test_phone_login_rejects_wrong_password(
    db_session: AsyncSession,
    cache_store: MemoryCacheStore,
) -> None:
    # Arrange
    phone = f"+1202{uuid4().int % 10_000_000:07d}"
    await register_with_phone_password(
        PhoneRegisterRequest(phone=phone, password="Password123", display_name="Phone Login User"),
        db_session,
        cache_store,
    )

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await login_with_phone_password(phone, "WrongPassword123", db_session, cache_store)


@pytest.mark.asyncio
async def test_refresh_login_rotates_refresh_token_and_rejects_old_token(
    db_session: AsyncSession,
    cache_store: MemoryCacheStore,
) -> None:
    # Arrange
    email = f"service-refresh-{uuid4().hex}@example.com"
    registered = await register_with_email_password(
        EmailRegisterRequest(email=email, password="Password123", display_name="Refresh User"),
        db_session,
        cache_store,
    )

    # Act
    refreshed = await refresh_login(registered.refresh_token, db_session, cache_store)

    # Assert
    assert refreshed.access_token != registered.access_token
    assert refreshed.refresh_token != registered.refresh_token
    assert decode_access_token(refreshed.access_token).user_id == registered.user.id
    assert decode_refresh_token(refreshed.refresh_token).user_id == registered.user.id
    assert cache_store.take_calls == 1
    assert cache_store.get_calls == 0

    with pytest.raises(InvalidCredentialsError):
        await refresh_login(registered.refresh_token, db_session, cache_store)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(
    db_session: AsyncSession,
    cache_store: MemoryCacheStore,
) -> None:
    # Arrange
    email = f"service-logout-{uuid4().hex}@example.com"
    registered = await register_with_email_password(
        EmailRegisterRequest(email=email, password="Password123", display_name="Logout User"),
        db_session,
        cache_store,
    )

    # Act
    await logout_by_token(registered.refresh_token, cache_store)

    # Assert
    assert cache_store.take_calls == 1
    assert cache_store.get_calls == 0
    with pytest.raises(InvalidCredentialsError):
        await refresh_login(registered.refresh_token, db_session, cache_store)
