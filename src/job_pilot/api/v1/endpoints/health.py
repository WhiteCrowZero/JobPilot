from fastapi import APIRouter

from job_pilot.core.config import settings

router = APIRouter()


def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "env": settings.APP_ENV,
    }


@router.get("", summary="Health check")
async def read_health() -> dict[str, str]:
    return health_check()


@router.get("/", include_in_schema=False)
async def read_health_slash() -> dict[str, str]:
    return health_check()
