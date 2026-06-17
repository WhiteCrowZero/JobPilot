from __future__ import annotations

import httpx
import pytest

from tests.api.endpoints import JOB_TARGETS_ENDPOINT


@pytest.mark.asyncio
async def test_job_targets_http_requires_bearer_token(api_client: httpx.AsyncClient) -> None:
    """目标岗位 HTTP 层仍需校验 bearer token。"""

    response = await api_client.get(JOB_TARGETS_ENDPOINT)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
