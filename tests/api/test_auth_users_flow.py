from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.users.enums import UserStatus
from job_pilot.modules.users.models import User
from tests.api.endpoints import (
    AUTH_LOGIN_EMAIL_ENDPOINT,
    AUTH_LOGIN_PHONE_ENDPOINT,
    AUTH_LOGOUT_ENDPOINT,
    AUTH_REFRESH_ENDPOINT,
    AUTH_REGISTER_EMAIL_ENDPOINT,
    AUTH_REGISTER_PHONE_ENDPOINT,
    USERS_ME_ENDPOINT,
)


@pytest.fixture(autouse=True)
def use_fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_hash_password(password: str) -> str:
        return f"test-hash:{password}"

    def fake_verify_password(plain_password: str, hashed_password: str) -> bool:
        return hashed_password == fake_hash_password(plain_password)

    monkeypatch.setattr("job_pilot.modules.auth.service.hash_password", fake_hash_password)
    monkeypatch.setattr("job_pilot.modules.auth.service.verify_password", fake_verify_password)


async def disable_user(user_id: int, db_session: AsyncSession) -> None:
    """将用户状态改为禁用，用于构造认证失败场景。"""

    await db_session.execute(
        update(User).where(User.id == user_id).values(status=UserStatus.DISABLED)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_email_register_login_refresh_and_read_current_user(
    api_client: httpx.AsyncClient,
) -> None:
    # Arrange
    email = f"user-{uuid4().hex}@example.com"
    password = "Password123"

    # Act
    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": email,
            "password": password,
            "display_name": "Job Pilot User",
        },
    )

    # Assert
    assert register_response.status_code == 201
    register_payload = register_response.json()
    assert register_payload["token_type"] == "bearer"
    assert register_payload["access_token"]
    assert register_payload["refresh_token"]
    assert register_payload["user"]["profile"]["display_name"] == "Job Pilot User"

    # Act
    me_response = await api_client.get(
        USERS_ME_ENDPOINT,
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    # Assert
    assert me_response.status_code == 200
    assert me_response.json()["id"] == register_payload["user"]["id"]

    # Act
    login_response = await api_client.post(
        AUTH_LOGIN_EMAIL_ENDPOINT,
        json={"email": email, "password": password},
    )

    # Assert
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["access_token"]
    assert login_payload["refresh_token"]

    # Act
    refresh_response = await api_client.post(
        AUTH_REFRESH_ENDPOINT,
        json={"refresh_token": login_payload["refresh_token"]},
    )

    # Assert
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["access_token"] != login_payload["access_token"]
    assert refresh_payload["refresh_token"] != login_payload["refresh_token"]

    # Act
    stale_refresh_response = await api_client.post(
        AUTH_REFRESH_ENDPOINT,
        json={"refresh_token": login_payload["refresh_token"]},
    )

    # Assert
    assert stale_refresh_response.status_code == 401
    assert stale_refresh_response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_phone_register_login_and_duplicate_phone(api_client: httpx.AsyncClient) -> None:
    # Arrange
    phone = f"+1202{uuid4().int % 10_000_000:07d}"
    password = "Password123"
    payload = {
        "phone": phone,
        "password": password,
        "display_name": "Phone User",
    }

    # Act
    register_response = await api_client.post(AUTH_REGISTER_PHONE_ENDPOINT, json=payload)
    duplicate_response = await api_client.post(AUTH_REGISTER_PHONE_ENDPOINT, json=payload)
    login_response = await api_client.post(
        AUTH_LOGIN_PHONE_ENDPOINT,
        json={"phone": phone, "password": password},
    )

    # Assert
    assert register_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["code"] == "AUTH_IDENTITY_ALREADY_EXISTS"
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_email_register_rejects_duplicate_email(api_client: httpx.AsyncClient) -> None:
    # Arrange
    email = f"duplicate-{uuid4().hex}@example.com"
    payload = {
        "email": email,
        "password": "Password123",
        "display_name": "Duplicate User",
    }

    # Act
    first_response = await api_client.post(AUTH_REGISTER_EMAIL_ENDPOINT, json=payload)
    second_response = await api_client.post(AUTH_REGISTER_EMAIL_ENDPOINT, json=payload)

    # Assert
    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["code"] == "AUTH_IDENTITY_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(api_client: httpx.AsyncClient) -> None:
    # Arrange
    email = f"invalid-password-{uuid4().hex}@example.com"
    await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": email,
            "password": "Password123",
            "display_name": "Invalid Password User",
        },
    )

    # Act
    response = await api_client.post(
        AUTH_LOGIN_EMAIL_ENDPOINT,
        json={"email": email, "password": "WrongPassword123"},
    )

    # Assert
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_email_register_rejects_weak_password(api_client: httpx.AsyncClient) -> None:
    # Arrange
    payload = {
        "email": f"weak-password-{uuid4().hex}@example.com",
        "password": "password",
        "display_name": "Weak Password User",
    }

    # Act
    response = await api_client.post(AUTH_REGISTER_EMAIL_ENDPOINT, json=payload)

    # Assert
    assert response.status_code == 422
    assert response.json()["code"] == "WEAK_PASSWORD"


@pytest.mark.asyncio
async def test_read_current_user_without_token_returns_401(
    api_client: httpx.AsyncClient,
) -> None:
    # Arrange & Act
    response = await api_client.get(USERS_ME_ENDPOINT)

    # Assert
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_read_current_user_with_refresh_token_returns_invalid_token_type(
    api_client: httpx.AsyncClient,
) -> None:
    # Arrange
    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": f"refresh-on-me-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": "Refresh Token User",
        },
    )
    refresh_token = register_response.json()["refresh_token"]

    # Act
    response = await api_client.get(
        USERS_ME_ENDPOINT,
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    # Assert
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN_TYPE"


@pytest.mark.asyncio
async def test_disabled_user_cannot_login(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Arrange
    email = f"disabled-login-{uuid4().hex}@example.com"
    password = "Password123"
    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": email,
            "password": password,
            "display_name": "Disabled Login User",
        },
    )
    await disable_user(register_response.json()["user"]["id"], db_session)

    # Act
    response = await api_client.post(
        AUTH_LOGIN_EMAIL_ENDPOINT,
        json={"email": email, "password": password},
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


@pytest.mark.asyncio
async def test_disabled_user_cannot_refresh(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Arrange
    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": f"disabled-refresh-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": "Disabled Refresh User",
        },
    )
    register_payload = register_response.json()
    await disable_user(register_payload["user"]["id"], db_session)

    # Act
    response = await api_client.post(
        AUTH_REFRESH_ENDPOINT,
        json={"refresh_token": register_payload["refresh_token"]},
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


@pytest.mark.asyncio
async def test_disabled_user_cannot_access_active_user_endpoint(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Arrange
    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": f"disabled-me-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": "Disabled Me User",
        },
    )
    register_payload = register_response.json()
    await disable_user(register_payload["user"]["id"], db_session)

    # Act
    response = await api_client.get(
        USERS_ME_ENDPOINT,
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        (
            AUTH_REGISTER_PHONE_ENDPOINT,
            {
                "phone": "13812345678",
                "password": "Password123",
                "display_name": "Invalid Phone User",
            },
        ),
        (
            AUTH_LOGIN_PHONE_ENDPOINT,
            {
                "phone": "13812345678",
                "password": "Password123",
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_phone_auth_rejects_invalid_phone_format(
    api_client: httpx.AsyncClient,
    endpoint: str,
    payload: dict[str, str],
) -> None:
    # Act
    response = await api_client.post(endpoint, json=payload)

    # Assert
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(api_client: httpx.AsyncClient) -> None:
    # Arrange
    email = f"logout-{uuid4().hex}@example.com"
    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": email,
            "password": "Password123",
            "display_name": "Logout User",
        },
    )
    refresh_token = register_response.json()["refresh_token"]

    # Act
    logout_response = await api_client.post(
        AUTH_LOGOUT_ENDPOINT,
        json={"refresh_token": refresh_token},
    )
    refresh_response = await api_client.post(
        AUTH_REFRESH_ENDPOINT,
        json={"refresh_token": refresh_token},
    )

    # Assert
    assert logout_response.status_code == 200
    assert logout_response.json()["status"] == "ok"
    assert refresh_response.status_code == 401
    assert refresh_response.json()["code"] == "INVALID_CREDENTIALS"
