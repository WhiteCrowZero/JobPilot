from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.endpoints import (
    AUTH_REGISTER_EMAIL_ENDPOINT,
    USER_SKILLS_ENDPOINT,
    user_skill_endpoint,
)
from tests.helpers.workbench import seed_test_skill, truncate_user_skill_tables


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
            "email": f"user-skills-{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": display_name,
        },
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(register_payload: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {register_payload['access_token']}"}


@pytest.mark.asyncio
async def test_user_skill_api_create_update_archive_and_restore(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        skill = await seed_test_skill(db_session, "Python")
        user_payload = await register_api_user(api_client, "Skill API User")
        headers = auth_headers(user_payload)

        create_response = await api_client.post(
            USER_SKILLS_ENDPOINT,
            headers=headers,
            json={
                "skill_id": skill.id,
                "proficiency_level": 2,
                "interest_level": 5,
                "evidence": "Side project",
            },
        )
        list_response = await api_client.get(USER_SKILLS_ENDPOINT, headers=headers)
        update_response = await api_client.patch(
            user_skill_endpoint(skill.id),
            headers=headers,
            json={
                "proficiency_level": 4,
                "note": "Focus on production experience",
            },
        )
        archive_response = await api_client.delete(user_skill_endpoint(skill.id), headers=headers)
        empty_list_response = await api_client.get(USER_SKILLS_ENDPOINT, headers=headers)
        restore_response = await api_client.post(
            USER_SKILLS_ENDPOINT,
            headers=headers,
            json={
                "skill_id": skill.id,
                "proficiency_level": 5,
                "interest_level": 3,
            },
        )

        assert create_response.status_code == 200
        created_payload = create_response.json()
        assert created_payload["skill_id"] == skill.id
        assert created_payload["status"] == "active"
        assert created_payload["evidence"] == "Side project"

        assert list_response.status_code == 200
        assert [item["skill_id"] for item in list_response.json()["items"]] == [skill.id]

        assert update_response.status_code == 200
        assert update_response.json()["proficiency_level"] == 4
        assert update_response.json()["note"] == "Focus on production experience"

        assert archive_response.status_code == 200
        assert archive_response.json()["status"] == "archived"
        assert archive_response.json()["archived_at"] is not None

        assert empty_list_response.status_code == 200
        assert empty_list_response.json()["items"] == []

        assert restore_response.status_code == 200
        assert restore_response.json()["id"] == created_payload["id"]
        assert restore_response.json()["status"] == "active"
        assert restore_response.json()["archived_at"] is None
        assert restore_response.json()["proficiency_level"] == 5
        assert restore_response.json()["evidence"] == "Side project"
        assert restore_response.json()["note"] == "Focus on production experience"
    finally:
        await truncate_user_skill_tables(db_session)


@pytest.mark.asyncio
async def test_user_skill_api_rejects_missing_standard_skill(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        user_payload = await register_api_user(api_client, "Missing Skill User")

        response = await api_client.post(
            USER_SKILLS_ENDPOINT,
            headers=auth_headers(user_payload),
            json={"skill_id": 999_999},
        )

        assert response.status_code == 404
        assert response.json()["code"] == "STANDARD_SKILL_NOT_FOUND"
    finally:
        await truncate_user_skill_tables(db_session)


@pytest.mark.asyncio
async def test_user_skill_api_hides_profiles_across_users(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        skill = await seed_test_skill(db_session, "Redis")
        owner_payload = await register_api_user(api_client, "Owner")
        other_payload = await register_api_user(api_client, "Other")

        create_response = await api_client.post(
            USER_SKILLS_ENDPOINT,
            headers=auth_headers(owner_payload),
            json={"skill_id": skill.id, "proficiency_level": 4},
        )
        other_update_response = await api_client.patch(
            user_skill_endpoint(skill.id),
            headers=auth_headers(other_payload),
            json={"proficiency_level": 3},
        )
        other_list_response = await api_client.get(
            USER_SKILLS_ENDPOINT,
            headers=auth_headers(other_payload),
        )

        assert create_response.status_code == 200
        assert other_update_response.status_code == 404
        assert other_update_response.json()["code"] == "USER_SKILL_NOT_FOUND"
        assert other_list_response.status_code == 200
        assert other_list_response.json()["items"] == []
    finally:
        await truncate_user_skill_tables(db_session)
