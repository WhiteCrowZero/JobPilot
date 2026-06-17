from __future__ import annotations

import httpx
import pytest

from tests.api.endpoints import job_detail_endpoint


@pytest.mark.asyncio
async def test_read_missing_job_post_returns_404(api_client: httpx.AsyncClient) -> None:
    """岗位详情 HTTP 层把业务 NotFound 映射为统一 404 响应。"""

    response = await api_client.get(job_detail_endpoint(999_999))

    assert response.status_code == 404
    assert response.json()["code"] == "JOB_POST_NOT_FOUND"
