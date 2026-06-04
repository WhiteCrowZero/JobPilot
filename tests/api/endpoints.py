from __future__ import annotations

from job_pilot.core.config import settings


def api_path(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{settings.API_PREFIX}/{settings.API_VERSION}{normalized_path}"


HEALTH_ENDPOINT = api_path("/health")
HEALTH_READINESS_ENDPOINT = api_path("/health/readiness")
