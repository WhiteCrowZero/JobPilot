from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.endpoints import (
    AUTH_REGISTER_EMAIL_ENDPOINT,
    job_match_job_coverage_endpoint,
    job_match_target_coverage_endpoint,
    job_match_target_skills_endpoint,
)
from tests.helpers.workbench import (
    seed_test_job_post,
    seed_test_job_post_skills,
    seed_test_skills,
    seed_test_target,
    truncate_workbench_tables,
)


@pytest.fixture(autouse=True)
def use_fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_hash_password(password: str) -> str:
        return f"test-hash:{password}"

    def fake_verify_password(plain_password: str, hashed_password: str) -> bool:
        return hashed_password == fake_hash_password(plain_password)

    monkeypatch.setattr("job_pilot.modules.auth.service.hash_password", fake_hash_password)
    monkeypatch.setattr("job_pilot.modules.auth.service.verify_password", fake_verify_password)


async def register_api_user(
    api_client: httpx.AsyncClient,
    *,
    display_name: str,
) -> dict[str, object]:
    """注册接口测试用户并返回 token payload。"""

    response = await api_client.post(
        AUTH_REGISTER_EMAIL_ENDPOINT,
        json={
            "email": f"{uuid4().hex}@example.com",
            "password": "Password123",
            "display_name": display_name,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_analyze_job_skill_coverage_requires_login(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        job_post = await seed_test_job_post(db_session, title="Backend Engineer")

        response = await api_client.get(job_match_job_coverage_endpoint(job_post.id))

        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_CREDENTIALS"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_target_skill_coverage_hides_other_users_target(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        owner_payload = await register_api_user(api_client, display_name="Owner")
        other_payload = await register_api_user(api_client, display_name="Other")
        owner_user = owner_payload["user"]
        assert isinstance(owner_user, dict)
        owner_id = owner_user["id"]
        assert isinstance(owner_id, int)
        job_post = await seed_test_job_post(db_session, title="Backend Engineer")
        target = await seed_test_target(
            db_session,
            user_id=owner_id,
            job_post_id=job_post.id,
            is_primary=True,
        )

        response = await api_client.get(
            job_match_target_coverage_endpoint(target.id),
            headers={"Authorization": f"Bearer {other_payload['access_token']}"},
        )

        assert response.status_code == 404
        assert response.json()["code"] == "JOB_TARGET_FOR_MATCH_NOT_FOUND"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_job_skill_coverage_returns_no_skill_data(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user_payload = await register_api_user(api_client, display_name="User")
        job_post = await seed_test_job_post(db_session, title="Backend Engineer")

        response = await api_client.get(
            job_match_job_coverage_endpoint(job_post.id),
            headers={"Authorization": f"Bearer {user_payload['access_token']}"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["analysis_status"] == "no_job_skill_data"
        assert payload["coverage_score"] is None
        assert payload["required_skill_count"] == 0
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_job_skill_coverage_rejects_invalid_required_level(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user_payload = await register_api_user(api_client, display_name="User")
        job_post = await seed_test_job_post(db_session, title="Backend Engineer")

        response = await api_client.get(
            f"{job_match_job_coverage_endpoint(job_post.id)}?required_level=6",
            headers={"Authorization": f"Bearer {user_payload['access_token']}"},
        )

        assert response.status_code == 422
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_target_skill_summary_returns_sorted_skills(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user_payload = await register_api_user(api_client, display_name="User")
        user = user_payload["user"]
        assert isinstance(user, dict)
        user_id = user["id"]
        assert isinstance(user_id, int)
        python, redis, mysql = await seed_test_skills(db_session, ["Python", "Redis", "MySQL"])
        first_job = await seed_test_job_post(db_session, title="Backend Engineer")
        second_job = await seed_test_job_post(db_session, title="Platform Engineer")
        await seed_test_job_post_skills(
            db_session,
            job_post_id=first_job.id,
            skill_ids=[python.id, redis.id],
        )
        await seed_test_job_post_skills(
            db_session,
            job_post_id=second_job.id,
            skill_ids=[python.id, mysql.id],
        )
        await seed_test_target(
            db_session,
            user_id=user_id,
            job_post_id=first_job.id,
            is_primary=True,
        )
        await seed_test_target(db_session, user_id=user_id, job_post_id=second_job.id)

        response = await api_client.get(
            job_match_target_skills_endpoint(),
            headers={"Authorization": f"Bearer {user_payload['access_token']}"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["target_count"] == 2
        assert payload["primary_job_post_id"] == first_job.id
        assert [item["skill_name"] for item in payload["items"]] == ["Python", "MySQL", "Redis"]
        assert [item["target_count"] for item in payload["items"]] == [2, 1, 1]
        assert payload["items"][0]["has_user_skill"] is False
        assert "is_user_owned" not in payload["items"][0]
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_target_skill_summary_rejects_invalid_limit(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user_payload = await register_api_user(api_client, display_name="User")

        response = await api_client.get(
            f"{job_match_target_skills_endpoint()}?limit=0",
            headers={"Authorization": f"Bearer {user_payload['access_token']}"},
        )

        assert response.status_code == 422
    finally:
        await truncate_workbench_tables(db_session)
