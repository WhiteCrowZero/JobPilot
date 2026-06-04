from __future__ import annotations

import httpx
import pytest

from tests.api.endpoints import HEALTH_ENDPOINT, HEALTH_READINESS_ENDPOINT

pytestmark = pytest.mark.smoke

LIVE_BASE_URL = "http://127.0.0.1:8000"


def live_url(endpoint: str) -> str:
    return f"{LIVE_BASE_URL}{endpoint}"


def test_live_read_health_returns_ok() -> None:
    response = httpx.get(live_url(HEALTH_ENDPOINT), timeout=5)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_live_read_readiness_reports_all_resources_healthy() -> None:
    response = httpx.get(live_url(HEALTH_READINESS_ENDPOINT), timeout=10)

    assert response.status_code == 200
    response_data = response.json()
    assert response_data == {
        "database": True,
        "redis": True,
        "message_queue": True,
    }
