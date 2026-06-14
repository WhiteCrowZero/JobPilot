from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.endpoints import (
    AUTH_REGISTER_EMAIL_ENDPOINT,
    JOB_COLLECTION_FOLDERS_ENDPOINT,
    JOB_COLLECTIONS_ENDPOINT,
    job_collection_endpoint,
    job_collection_folder_default_endpoint,
    job_collection_folder_endpoint,
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
            "email": f"job-collections-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": display_name,
        },
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(register_payload: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {register_payload['access_token']}"}


@pytest.mark.asyncio
async def test_job_collection_api_folder_collect_update_remove_and_restore(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        job_post = await seed_test_job_post(db_session)
        user_payload = await register_api_user(api_client, "Collection API User")
        headers = auth_headers(user_payload)

        folder_response = await api_client.post(
            JOB_COLLECTION_FOLDERS_ENDPOINT,
            headers=headers,
            json={"name": "Backend", "sort_order": 1},
        )
        folder_payload = folder_response.json()
        folders_response = await api_client.get(JOB_COLLECTION_FOLDERS_ENDPOINT, headers=headers)
        default_folder_payload = next(
            item for item in folders_response.json() if item["is_default"] is True
        )
        collect_response = await api_client.post(
            JOB_COLLECTIONS_ENDPOINT,
            headers=headers,
            json={
                "job_post_id": job_post.id,
                "folder_id": folder_payload["id"],
                "note": "Worth tracking",
            },
        )
        collection_payload = collect_response.json()
        list_response = await api_client.get(JOB_COLLECTIONS_ENDPOINT, headers=headers)
        update_response = await api_client.patch(
            job_collection_endpoint(collection_payload["id"]),
            headers=headers,
            json={"note": "Updated note", "folder_id": None},
        )
        archive_folder_response = await api_client.delete(
            job_collection_folder_endpoint(folder_payload["id"]),
            headers=headers,
        )
        archive_default_folder_response = await api_client.delete(
            job_collection_folder_endpoint(default_folder_payload["id"]),
            headers=headers,
        )
        remove_response = await api_client.delete(
            job_collection_endpoint(collection_payload["id"]),
            headers=headers,
        )
        empty_list_response = await api_client.get(JOB_COLLECTIONS_ENDPOINT, headers=headers)
        restore_response = await api_client.post(
            JOB_COLLECTIONS_ENDPOINT,
            headers=headers,
            json={"job_post_id": job_post.id},
        )

        assert folder_response.status_code == 200
        assert folder_payload["name"] == "Backend"
        assert folder_payload["is_default"] is False
        assert folders_response.status_code == 200
        assert [item["name"] for item in folders_response.json()] == ["默认收藏夹", "Backend"]

        assert collect_response.status_code == 200
        assert collection_payload["job_post_id"] == job_post.id
        assert collection_payload["folder_id"] == folder_payload["id"]
        assert collection_payload["note"] == "Worth tracking"

        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()["items"]] == [collection_payload["id"]]

        assert update_response.status_code == 200
        assert update_response.json()["note"] == "Updated note"
        assert update_response.json()["folder_id"] == default_folder_payload["id"]

        assert archive_folder_response.status_code == 200
        assert archive_folder_response.json()["status"] == "archived"
        assert archive_default_folder_response.status_code == 409
        assert archive_default_folder_response.json()["code"] == (
            "DEFAULT_JOB_COLLECTION_FOLDER_CANNOT_ARCHIVE"
        )

        assert remove_response.status_code == 200
        assert remove_response.json()["status"] == "removed"
        assert remove_response.json()["removed_at"] is not None

        assert empty_list_response.status_code == 200
        assert empty_list_response.json()["items"] == []

        assert restore_response.status_code == 200
        assert restore_response.json()["id"] == collection_payload["id"]
        assert restore_response.json()["status"] == "active"
        assert restore_response.json()["removed_at"] is None
        assert restore_response.json()["folder_id"] == default_folder_payload["id"]
        assert restore_response.json()["note"] == "Updated note"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_job_collection_api_rejects_missing_job(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user_payload = await register_api_user(api_client, "Missing Job User")

        response = await api_client.post(
            JOB_COLLECTIONS_ENDPOINT,
            headers=auth_headers(user_payload),
            json={"job_post_id": 999_999},
        )

        assert response.status_code == 404
        assert response.json()["code"] == "JOB_COLLECTION_JOB_POST_NOT_FOUND"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_job_collection_api_can_switch_default_folder(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        job_post = await seed_test_job_post(db_session)
        user_payload = await register_api_user(api_client, "Default Folder User")
        headers = auth_headers(user_payload)

        folder_response = await api_client.post(
            JOB_COLLECTION_FOLDERS_ENDPOINT,
            headers=headers,
            json={"name": "Backend"},
        )
        folders_response = await api_client.get(JOB_COLLECTION_FOLDERS_ENDPOINT, headers=headers)
        old_default_payload = next(
            item for item in folders_response.json() if item["is_default"] is True
        )
        switch_response = await api_client.post(
            job_collection_folder_default_endpoint(folder_response.json()["id"]),
            headers=headers,
        )
        collect_response = await api_client.post(
            JOB_COLLECTIONS_ENDPOINT,
            headers=headers,
            json={"job_post_id": job_post.id},
        )
        updated_folders_response = await api_client.get(
            JOB_COLLECTION_FOLDERS_ENDPOINT,
            headers=headers,
        )
        archive_old_default_response = await api_client.delete(
            job_collection_folder_endpoint(old_default_payload["id"]),
            headers=headers,
        )

        assert folder_response.status_code == 200
        assert switch_response.status_code == 200
        assert switch_response.json()["is_default"] is True

        assert collect_response.status_code == 200
        assert collect_response.json()["folder_id"] == folder_response.json()["id"]

        assert updated_folders_response.status_code == 200
        assert [
            item["id"] for item in updated_folders_response.json() if item["is_default"] is True
        ] == [folder_response.json()["id"]]

        assert archive_old_default_response.status_code == 200
        assert archive_old_default_response.json()["status"] == "archived"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_job_collection_api_hides_collections_across_users(
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

        create_response = await api_client.post(
            JOB_COLLECTIONS_ENDPOINT,
            headers=owner_headers,
            json={"job_post_id": job_post.id},
        )
        collection_id = create_response.json()["id"]
        other_update_response = await api_client.patch(
            job_collection_endpoint(collection_id),
            headers=other_headers,
            json={"note": "Cross user"},
        )
        other_remove_response = await api_client.delete(
            job_collection_endpoint(collection_id),
            headers=other_headers,
        )
        other_list_response = await api_client.get(
            JOB_COLLECTIONS_ENDPOINT,
            headers=other_headers,
        )

        assert create_response.status_code == 200
        assert other_update_response.status_code == 404
        assert other_update_response.json()["code"] == "JOB_COLLECTION_NOT_FOUND"
        assert other_remove_response.status_code == 404
        assert other_remove_response.json()["code"] == "JOB_COLLECTION_NOT_FOUND"
        assert other_list_response.status_code == 200
        assert other_list_response.json()["items"] == []
    finally:
        await truncate_workbench_tables(db_session)
