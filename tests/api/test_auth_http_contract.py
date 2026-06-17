from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from tests.api.endpoints import AUTH_REGISTER_EMAIL_ENDPOINT, USERS_ME_ENDPOINT


@pytest.fixture(autouse=True)
def use_fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """API 契约测试替换慢哈希，避免 HTTP 层测试被密码哈希耗时影响。"""

    def fake_hash_password(password: str) -> str:
        return f"test-hash:{password}"

    def fake_verify_password(plain_password: str, hashed_password: str) -> bool:
        return hashed_password == fake_hash_password(plain_password)

    monkeypatch.setattr("job_pilot.modules.auth.service.hash_password", fake_hash_password)
    monkeypatch.setattr("job_pilot.modules.auth.service.verify_password", fake_verify_password)


@pytest.mark.asyncio
async def test_email_register_http_contract_and_read_current_user(
    api_client: httpx.AsyncClient,
) -> None:
    """认证 HTTP 层能完成请求体解析、响应序列化和 bearer 认证。"""

    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": f"user-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": "Job Pilot User",
        },
    )
    payload = register_response.json()

    me_response = await api_client.get(
        USERS_ME_ENDPOINT,
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )

    assert register_response.status_code == 201
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["profile"]["display_name"] == "Job Pilot User"
    assert me_response.status_code == 200
    assert me_response.json()["id"] == payload["user"]["id"]


@pytest.mark.asyncio
async def test_read_current_user_without_token_returns_401(
    api_client: httpx.AsyncClient,
) -> None:
    """未携带 token 访问当前用户接口返回统一 401。"""

    response = await api_client.get(USERS_ME_ENDPOINT)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
