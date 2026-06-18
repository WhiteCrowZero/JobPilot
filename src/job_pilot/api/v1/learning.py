from __future__ import annotations

from fastapi import APIRouter

from job_pilot.modules.knowledge.router import router as knowledge_router

router = APIRouter()

router.include_router(knowledge_router, tags=["knowledge"])
