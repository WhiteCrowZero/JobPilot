from __future__ import annotations

from fastapi import APIRouter

from job_pilot.api import health
from job_pilot.api.v1.jobs import router as jobs_router
from job_pilot.api.v1.learning import router as learning_router
from job_pilot.api.v1.users import router as user_router

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(user_router, prefix="/user")
api_router.include_router(jobs_router, prefix="/jobs")
api_router.include_router(learning_router, prefix="/learning")
