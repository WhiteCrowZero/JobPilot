from __future__ import annotations

from job_pilot.core.config import settings


def api_path(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{settings.API_PREFIX}/{settings.API_VERSION}{normalized_path}"


HEALTH_ENDPOINT = api_path("/health")
HEALTH_READINESS_ENDPOINT = api_path("/health/readiness")
AUTH_REGISTER_EMAIL_ENDPOINT = api_path("/auth/register/email")
AUTH_REGISTER_PHONE_ENDPOINT = api_path("/auth/register/phone")
AUTH_LOGIN_EMAIL_ENDPOINT = api_path("/auth/login/email")
AUTH_LOGIN_PHONE_ENDPOINT = api_path("/auth/login/phone")
AUTH_REFRESH_ENDPOINT = api_path("/auth/refresh")
AUTH_LOGOUT_ENDPOINT = api_path("/auth/logout")
USERS_ME_ENDPOINT = api_path("/users/me")
JOBS_ENDPOINT = api_path("/jobs")
JOBS_FILTER_OPTIONS_ENDPOINT = api_path("/jobs/filter-options")


def job_detail_endpoint(job_post_id: int) -> str:
    return api_path(f"/jobs/{job_post_id}")
