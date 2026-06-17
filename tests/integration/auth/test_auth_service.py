from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.auth.contracts import (
    EmailRegisterCommand as EmailRegisterRequest,
)
from job_pilot.modules.auth.contracts import (
    PhoneRegisterCommand as PhoneRegisterRequest,
)
from job_pilot.modules.auth.enums import AuthProvider
from job_pilot.modules.auth.exceptions import InvalidCredentialsError
from job_pilot.modules.auth.models import AuthIdentity, AuthPasswordCredential
from job_pilot.modules.auth.utils.tokens import decode_access_token, decode_refresh_token


@pytest.fixture(autouse=True)
def use_fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """把慢哈希替换成确定性实现，让集成测试聚焦业务行为。"""

    def fake_hash_password(password: str) -> str:
        return f"test-hash:{password}"

    def fake_verify_password(plain_password: str, hashed_password: str) -> bool:
        return hashed_password == fake_hash_password(plain_password)

    monkeypatch.setattr("job_pilot.modules.auth.service.hash_password", fake_hash_password)
    monkeypatch.setattr("job_pilot.modules.auth.service.verify_password", fake_verify_password)


@pytest.mark.asyncio
async def test_register_with_email_password_creates_identity_credential_and_profile(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """通过公开库入口注册邮箱用户并验证持久化结果。"""

    email = f"service-register-{uuid4().hex}@example.com"

    response = await pilot.auth.register_with_email(
        EmailRegisterRequest(
            email=email,
            password="Password123",
            display_name="Service User",
        )
    )

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
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """通过公开库入口注册手机号用户。"""

    phone = f"+1202{uuid4().int % 10_000_000:07d}"

    response = await pilot.auth.register_with_phone(
        PhoneRegisterRequest(
            phone=phone,
            password="Password123",
            display_name="Phone User",
        )
    )

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
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """通过公开库入口登录并验证登录时间被更新。"""

    email = f"service-login-{uuid4().hex}@example.com"
    password = "Password123"
    await pilot.auth.register_with_email(
        EmailRegisterRequest(email=email, password=password, display_name="Login User")
    )

    response = await pilot.auth.login_with_email(email=email, password=password)

    assert response.user.last_login_at is not None

    identity_result = await db_session.execute(select(AuthIdentity))
    identity = identity_result.scalar_one()
    assert identity.last_login_at is not None


@pytest.mark.asyncio
async def test_phone_login_rejects_wrong_password(pilot: JobPilot) -> None:
    """手机号密码错误时公开入口抛出统一认证异常。"""

    phone = f"+1202{uuid4().int % 10_000_000:07d}"
    await pilot.auth.register_with_phone(
        PhoneRegisterRequest(
            phone=phone,
            password="Password123",
            display_name="Phone Login User",
        )
    )

    with pytest.raises(InvalidCredentialsError):
        await pilot.auth.login_with_phone(phone=phone, password="WrongPassword123")


@pytest.mark.asyncio
async def test_refresh_login_rotates_refresh_token_and_rejects_old_token(
    pilot: JobPilot,
) -> None:
    """刷新登录会轮换 refresh token，旧 token 不能再次使用。"""

    email = f"service-refresh-{uuid4().hex}@example.com"
    registered = await pilot.auth.register_with_email(
        EmailRegisterRequest(
            email=email,
            password="Password123",
            display_name="Refresh User",
        )
    )

    refreshed = await pilot.auth.refresh_login(refresh_token=registered.refresh_token)

    assert refreshed.access_token != registered.access_token
    assert refreshed.refresh_token != registered.refresh_token
    assert decode_access_token(refreshed.access_token).user_id == registered.user.id
    assert decode_refresh_token(refreshed.refresh_token).user_id == registered.user.id

    with pytest.raises(InvalidCredentialsError):
        await pilot.auth.refresh_login(refresh_token=registered.refresh_token)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(pilot: JobPilot) -> None:
    """退出登录会撤销 refresh token。"""

    email = f"logout-{uuid4().hex}@example.com"
    registered = await pilot.auth.register_with_email(
        EmailRegisterRequest(
            email=email,
            password="Password123",
            display_name="Logout User",
        )
    )

    await pilot.auth.logout(refresh_token=registered.refresh_token)

    with pytest.raises(InvalidCredentialsError):
        await pilot.auth.refresh_login(refresh_token=registered.refresh_token)
