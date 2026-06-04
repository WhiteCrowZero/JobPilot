from fastapi import APIRouter, Request

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


@router.get("/readiness", summary="Readiness check")
async def read_readiness(request: Request) -> dict[str, bool]:
    return await request.app.state.resources.health_check()
