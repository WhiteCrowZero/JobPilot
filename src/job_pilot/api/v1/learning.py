from __future__ import annotations

from fastapi import APIRouter

from job_pilot.modules.knowledge.router import router as knowledge_router
from job_pilot.modules.questions.router import router as questions_router
from job_pilot.modules.study_tasks.router import router as study_tasks_router

router = APIRouter()

router.include_router(knowledge_router, prefix="/knowledge", tags=["knowledge"])
router.include_router(questions_router, prefix="/questions", tags=["questions"])
router.include_router(study_tasks_router, prefix="/study-tasks", tags=["study-tasks"])
