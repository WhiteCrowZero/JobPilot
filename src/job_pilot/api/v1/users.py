from __future__ import annotations

from fastapi import APIRouter

from job_pilot.modules.auth.router import router as auth_router
from job_pilot.modules.user_skills.router import router as user_skills_router
from job_pilot.modules.users.router import router as users_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(user_skills_router, prefix="/skills", tags=["user-skills"])
router.include_router(users_router, tags=["users"])
