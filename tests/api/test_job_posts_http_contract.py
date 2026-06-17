from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.endpoints import JOBS_SEARCH_ENDPOINT, job_detail_endpoint
from tests.helpers.builders import (
    seed_test_job_post,
    seed_test_job_post_skills,
    seed_test_skills,
)
from tests.helpers.database import truncate_job_tables


@pytest.mark.asyncio
async def test_read_missing_job_post_returns_404(api_client: httpx.AsyncClient) -> None:
    """岗位详情 HTTP 层把业务 NotFound 映射为统一 404 响应。"""

    response = await api_client.get(job_detail_endpoint(999_999))

    assert response.status_code == 404
    assert response.json()["code"] == "JOB_POST_NOT_FOUND"


@pytest.mark.asyncio
async def test_search_job_posts_parses_repeated_skill_ids(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """岗位搜索 HTTP 层支持 repeated query list 参数。"""

    await truncate_job_tables(db_session)
    try:
        python, fastapi, redis = await seed_test_skills(
            db_session,
            ["Python", "FastAPI", "Redis"],
        )
        matched_job = await seed_test_job_post(db_session, title="Matched Backend")
        unmatched_job = await seed_test_job_post(db_session, title="Unmatched Backend")
        await seed_test_job_post_skills(
            db_session,
            job_post_id=matched_job.id,
            skill_ids=[python.id, fastapi.id],
        )
        await seed_test_job_post_skills(
            db_session,
            job_post_id=unmatched_job.id,
            skill_ids=[python.id, redis.id],
        )

        response = await api_client.get(
            JOBS_SEARCH_ENDPOINT,
            params=[("skill_ids", str(python.id)), ("skill_ids", str(fastapi.id))],
        )

        assert response.status_code == 200
        assert [item["title"] for item in response.json()["items"]] == ["Matched Backend"]
    finally:
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_search_job_posts_rejects_invalid_salary_range(
    api_client: httpx.AsyncClient,
) -> None:
    """岗位搜索 HTTP 层暴露 schema range 校验。"""

    response = await api_client.get(
        JOBS_SEARCH_ENDPOINT,
        params={"salary_min": "30000", "salary_max": "10000"},
    )

    assert response.status_code == 422
