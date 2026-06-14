from __future__ import annotations

from job_pilot.core.config import settings


def api_path(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{settings.API_PREFIX}/{settings.API_VERSION}{normalized_path}"


HEALTH_ENDPOINT = api_path("/health")
HEALTH_READINESS_ENDPOINT = api_path("/health/readiness")
AUTH_REGISTER_EMAIL_ENDPOINT = api_path("/user/auth/register/email")
AUTH_REGISTER_PHONE_ENDPOINT = api_path("/user/auth/register/phone")
AUTH_LOGIN_EMAIL_ENDPOINT = api_path("/user/auth/login/email")
AUTH_LOGIN_PHONE_ENDPOINT = api_path("/user/auth/login/phone")
AUTH_REFRESH_ENDPOINT = api_path("/user/auth/refresh")
AUTH_LOGOUT_ENDPOINT = api_path("/user/auth/logout")
USERS_ME_ENDPOINT = api_path("/user/me")
JOBS_SEARCH_ENDPOINT = api_path("/jobs/search")
JOBS_FILTER_OPTIONS_ENDPOINT = api_path("/jobs/filter-options")
JOB_SKILLS_ENDPOINT = api_path("/jobs/skills")
JOB_COLLECTIONS_ENDPOINT = api_path("/jobs/collections")
JOB_COLLECTION_FOLDERS_ENDPOINT = api_path("/jobs/collections/folders")
JOB_TARGETS_ENDPOINT = api_path("/jobs/targets")
USER_SKILLS_ENDPOINT = api_path("/user/skills")


def job_detail_endpoint(job_post_id: int) -> str:
    return api_path(f"/jobs/{job_post_id}")


def user_skill_endpoint(skill_id: int) -> str:
    return api_path(f"/user/skills/{skill_id}")


def job_collection_endpoint(collection_id: int) -> str:
    return api_path(f"/jobs/collections/{collection_id}")


def job_collection_folder_endpoint(folder_id: int) -> str:
    return api_path(f"/jobs/collections/folders/{folder_id}")


def job_target_endpoint(target_id: int) -> str:
    return api_path(f"/jobs/targets/{target_id}")
