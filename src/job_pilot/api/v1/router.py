from __future__ import annotations

from fastapi import APIRouter

from job_pilot.api import health
from job_pilot.modules.auth.router import router as auth_router
from job_pilot.modules.job_posts.router import router as job_posts_router
from job_pilot.modules.job_skills.router import router as job_skills_router
from job_pilot.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(job_posts_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(job_skills_router, prefix="/skills", tags=["skills"])
