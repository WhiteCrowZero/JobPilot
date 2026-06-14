from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.endpoints import (
    AUTH_REGISTER_EMAIL_ENDPOINT,
    JOB_TARGETS_ENDPOINT,
    job_target_endpoint,
)
from tests.helpers.workbench import seed_test_job_post, truncate_workbench_tables


@pytest.fixture(autouse=True)
def use_fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_hash_password(password: str) -> str:
        return f"test-hash:{password}"

    def fake_verify_password(plain_password: str, hashed_password: str) -> bool:
        return hashed_password == fake_hash_password(plain_password)

    monkeypatch.setattr("job_pilot.modules.auth.service.hash_password", fake_hash_password)
    monkeypatch.setattr("job_pilot.modules.auth.service.verify_password", fake_verify_password)


async def register_api_user(api_client: httpx.AsyncClient, display_name: str) -> dict[str, object]:
    """注册接口测试用户并返回 token 响应。"""

    response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": f"job-targets-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": display_name,
        },
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(register_payload: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {register_payload['access_token']}"}


@pytest.mark.asyncio
async def test_job_target_api_create_primary_update_archive_and_restore(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        backend_job = await seed_test_job_post(db_session, title="Backend Engineer")
        data_job = await seed_test_job_post(db_session, title="Data Engineer")
        user_payload = await register_api_user(api_client, "Target API User")
        headers = auth_headers(user_payload)

        backend_response = await api_client.post(
            JOB_TARGETS_ENDPOINT,
            headers=headers,
            json={
                "job_post_id": backend_job.id,
                "priority": 2,
                "is_primary": True,
                "note": "Backend target",
            },
        )
        data_response = await api_client.post(
            JOB_TARGETS_ENDPOINT,
            headers=headers,
            json={
                "job_post_id": data_job.id,
                "priority": 1,
                "is_primary": True,
            },
        )
        list_response = await api_client.get(JOB_TARGETS_ENDPOINT, headers=headers)
        complete_response = await api_client.patch(
            job_target_endpoint(data_response.json()["id"]),
            headers=headers,
            json={"status": "completed"},
        )
        archive_response = await api_client.delete(
            job_target_endpoint(backend_response.json()["id"]),
            headers=headers,
        )
        default_list_response = await api_client.get(JOB_TARGETS_ENDPOINT, headers=headers)
        archived_list_response = await api_client.get(
            JOB_TARGETS_ENDPOINT,
            headers=headers,
            params={"statuses": "archived"},
        )
        restore_response = await api_client.post(
            JOB_TARGETS_ENDPOINT,
            headers=headers,
            json={"job_post_id": backend_job.id},
        )

        assert backend_response.status_code == 200
        assert backend_response.json()["job_post_id"] == backend_job.id
        assert backend_response.json()["is_primary"] is True

        assert data_response.status_code == 200
        assert data_response.json()["job_post_id"] == data_job.id
        assert data_response.json()["is_primary"] is True

        assert list_response.status_code == 200
        assert [item["job_post_id"] for item in list_response.json()["items"]] == [
            data_job.id,
            backend_job.id,
        ]
        assert list_response.json()["items"][0]["is_primary"] is True
        assert list_response.json()["items"][1]["is_primary"] is False

        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"
        assert complete_response.json()["completed_at"] is not None
        assert complete_response.json()["is_primary"] is False

        assert archive_response.status_code == 200
        assert archive_response.json()["status"] == "archived"
        assert archive_response.json()["archived_at"] is not None

        assert default_list_response.status_code == 200
        assert default_list_response.json()["items"] == []

        assert archived_list_response.status_code == 200
        assert [item["job_post_id"] for item in archived_list_response.json()["items"]] == [
            backend_job.id
        ]

        assert restore_response.status_code == 200
        assert restore_response.json()["id"] == backend_response.json()["id"]
        assert restore_response.json()["status"] == "active"
        assert restore_response.json()["archived_at"] is None
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_job_target_api_rejects_missing_job_and_hides_cross_user_target(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        job_post = await seed_test_job_post(db_session)
        owner_payload = await register_api_user(api_client, "Owner")
        other_payload = await register_api_user(api_client, "Other")
        owner_headers = auth_headers(owner_payload)
        other_headers = auth_headers(other_payload)

        missing_job_response = await api_client.post(
            JOB_TARGETS_ENDPOINT,
            headers=owner_headers,
            json={"job_post_id": 999_999},
        )
        create_response = await api_client.post(
            JOB_TARGETS_ENDPOINT,
            headers=owner_headers,
            json={"job_post_id": job_post.id},
        )
        other_update_response = await api_client.patch(
            job_target_endpoint(create_response.json()["id"]),
            headers=other_headers,
            json={"note": "Cross user"},
        )
        other_list_response = await api_client.get(JOB_TARGETS_ENDPOINT, headers=other_headers)

        assert missing_job_response.status_code == 404
        assert missing_job_response.json()["code"] == "JOB_TARGET_JOB_POST_NOT_FOUND"

        assert create_response.status_code == 200
        assert other_update_response.status_code == 404
        assert other_update_response.json()["code"] == "JOB_TARGET_NOT_FOUND"
        assert other_list_response.status_code == 200
        assert other_list_response.json()["items"] == []
    finally:
        await truncate_workbench_tables(db_session)
