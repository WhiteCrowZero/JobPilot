from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from job_pilot.api.deps import JobPilotDep
from job_pilot.modules.questions.contracts import QuestionSearchQuery
from job_pilot.modules.questions.schemas import (
    QuestionDetailResponse,
    QuestionListResponse,
    QuestionSearchParams,
)

router = APIRouter()


@router.get("/search", response_model=QuestionListResponse)
async def search_questions(
    pilot: JobPilotDep,
    params: Annotated[QuestionSearchParams, Query()],
) -> QuestionListResponse:
    """查询题目列表，支持关键词、题型、难度、技能和知识点筛选。"""

    query = QuestionSearchQuery(**params.model_dump())
    return await pilot.learning.search_questions(query)


@router.get("/{question_id}", response_model=QuestionDetailResponse)
async def read_question_detail(
    question_id: Annotated[int, Path(gt=0)],
    pilot: JobPilotDep,
) -> QuestionDetailResponse:
    """读取题目详情。"""

    return await pilot.learning.get_question_detail(question_id=question_id)
