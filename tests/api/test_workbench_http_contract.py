from __future__ import annotations

import httpx
import pytest

from tests.api.endpoints import (
    JOB_COLLECTIONS_ENDPOINT,
    USER_SKILLS_ENDPOINT,
    job_match_target_skills_endpoint,
)


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [
        ("GET", JOB_COLLECTIONS_ENDPOINT),
        ("GET", USER_SKILLS_ENDPOINT),
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
