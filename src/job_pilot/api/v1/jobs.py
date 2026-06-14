from __future__ import annotations

from fastapi import APIRouter

from job_pilot.modules.job_collections.router import router as job_collections_router
from job_pilot.modules.job_posts.router import router as job_posts_router
from job_pilot.modules.job_skills.router import router as job_skills_router
from job_pilot.modules.job_targets.router import router as job_targets_router

router = APIRouter()

router.include_router(job_collections_router, prefix="/collections", tags=["job-collections"])
router.include_router(job_skills_router, prefix="/skills", tags=["job-skills"])
router.include_router(job_targets_router, prefix="/targets", tags=["job-targets"])
router.include_router(job_posts_router, tags=["jobs"])
