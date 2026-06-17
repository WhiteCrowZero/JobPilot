from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.endpoints import (
    AUTH_REGISTER_EMAIL_ENDPOINT,
    JOB_COLLECTION_FOLDERS_ENDPOINT,
    JOB_COLLECTIONS_ENDPOINT,
    USER_SKILLS_ENDPOINT,
    job_match_job_coverage_endpoint,
    job_match_target_skills_endpoint,
)


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [
        ("GET", JOB_COLLECTIONS_ENDPOINT),
        ("GET", USER_SKILLS_ENDPOINT),
        ("GET", job_match_job_coverage_endpoint(1)),
        ("GET", job_match_target_skills_endpoint()),
    ],
)
@pytest.mark.asyncio
async def test_workbench_http_requires_bearer_token(
    api_client: httpx.AsyncClient,
    method: str,
    endpoint: str,
) -> None:
    """工作台 HTTP 端点只保留认证契约测试，业务行为由 integration 覆盖。"""

    response = await api_client.request(method, endpoint)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


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
async def test_duplicate_collection_folder_name_returns_409(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """收藏夹重名冲突通过 HTTP 层返回 409。"""

    _ = db_session
    register_response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": f"folder-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": "Folder User",
        },
    )
    access_token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    first_response = await api_client.post(
        JOB_COLLECTION_FOLDERS_ENDPOINT,
        json={"name": "Backend"},
        headers=headers,
    )
    duplicate_response = await api_client.post(
        JOB_COLLECTION_FOLDERS_ENDPOINT,
        json={"name": "Backend"},
        headers=headers,
    )

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["code"] == "JOB_COLLECTION_FOLDER_NAME_CONFLICT"
