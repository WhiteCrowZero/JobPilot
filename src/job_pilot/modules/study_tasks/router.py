from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query
from starlette import status

from job_pilot.api.deps import CurrentActiveUserDep, JobPilotDep
from job_pilot.modules.study_tasks.contracts import (
    StudyTaskCreateCommand,
    StudyTaskGenerateFromTargetCommand,
    StudyTaskListQuery,
    StudyTaskQuestionAttemptCommand,
    StudyTaskQuestionSkipCommand,
    StudyTaskUpdateCommand,
)
from job_pilot.modules.study_tasks.schemas import (
    StudyTaskAttemptResponse,
    StudyTaskCreateRequest,
    StudyTaskDetailResponse,
    StudyTaskGenerateFromTargetRequest,
    StudyTaskGenerationResponse,
    StudyTaskListItem,
    StudyTaskListParams,
    StudyTaskListResponse,
    StudyTaskQuestionAttemptRequest,
    StudyTaskQuestionSkipRequest,
    StudyTaskUpdateRequest,
    StudyTaskUpdateResponse,
)

router = APIRouter()


@router.post("", response_model=StudyTaskListItem, status_code=status.HTTP_201_CREATED)
async def create_study_task(
    payload: StudyTaskCreateRequest,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> StudyTaskListItem:
    """手动创建当前用户学习任务。"""

    return await pilot.learning.create_study_task(
        user_id=current_user.id,
        payload=StudyTaskCreateCommand(
            skill_id=payload.skill_id,
            task_type=payload.task_type,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            estimated_minutes=payload.estimated_minutes,
            planned_start_date=payload.planned_start_date,
            due_date=payload.due_date,
            question_ids=payload.question_ids,
        ),
    )


@router.post("/targets/{target_id}/generate", response_model=StudyTaskGenerationResponse)
async def generate_study_tasks_from_target(
    target_id: Annotated[int, Path(gt=0)],
    payload: StudyTaskGenerateFromTargetRequest,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> StudyTaskGenerationResponse:
    """根据当前用户目标岗位生成学习任务。"""

    return await pilot.learning.generate_study_tasks_from_target(
        user_id=current_user.id,
        target_id=target_id,
        payload=StudyTaskGenerateFromTargetCommand(
            max_tasks=payload.max_tasks,
            question_count_per_task=payload.question_count_per_task,
            difficulty=payload.difficulty,
            include_weak_skills=payload.include_weak_skills,
            include_missing_skills=payload.include_missing_skills,
            due_days=payload.due_days,
            required_level=payload.required_level,
        ),
    )


@router.get("", response_model=StudyTaskListResponse)
async def list_study_tasks(
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
    params: Annotated[StudyTaskListParams, Query()],
) -> StudyTaskListResponse:
    """查询当前用户学习任务列表。"""

    return await pilot.learning.list_study_tasks(
        user_id=current_user.id,
        params=StudyTaskListQuery(
            statuses=params.statuses,
            skill_ids=params.skill_ids,
            page=params.page,
            page_size=params.page_size,
        ),
    )


@router.patch("/{task_id}", response_model=StudyTaskUpdateResponse)
async def update_study_task(
    task_id: Annotated[int, Path(gt=0)],
    payload: StudyTaskUpdateRequest,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> StudyTaskUpdateResponse:
    """更新当前用户学习任务本体。"""

    return await pilot.learning.update_study_task(
        user_id=current_user.id,
        task_id=task_id,
        payload=StudyTaskUpdateCommand(
            status=payload.status,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            estimated_minutes=payload.estimated_minutes,
            actual_minutes=payload.actual_minutes,
            planned_start_date=payload.planned_start_date,
            due_date=payload.due_date,
            fields_set=frozenset(payload.model_fields_set),
        ),
    )


@router.delete("/{task_id}", response_model=StudyTaskUpdateResponse)
async def archive_study_task(
    task_id: Annotated[int, Path(gt=0)],
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> StudyTaskUpdateResponse:
    """归档当前用户学习任务。"""

    return await pilot.learning.archive_study_task(
        user_id=current_user.id,
        task_id=task_id,
    )


@router.get("/{task_id}", response_model=StudyTaskDetailResponse)
async def read_study_task_detail(
    task_id: Annotated[int, Path(gt=0)],
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> StudyTaskDetailResponse:
    """读取当前用户学习任务详情。"""

    return await pilot.learning.get_study_task_detail(
        user_id=current_user.id,
        task_id=task_id,
    )


@router.post(
    "/{task_id}/questions/{task_question_id}/attempts",
    response_model=StudyTaskAttemptResponse,
)
async def submit_study_task_question_attempt(
    task_id: Annotated[int, Path(gt=0)],
    task_question_id: Annotated[int, Path(gt=0)],
    payload: StudyTaskQuestionAttemptRequest,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> StudyTaskAttemptResponse:
    """提交当前用户某个学习任务题目的作答。"""

    return await pilot.learning.submit_study_task_question_attempt(
        user_id=current_user.id,
        task_id=task_id,
        task_question_id=task_question_id,
        payload=StudyTaskQuestionAttemptCommand(
            selected_option_ids=payload.selected_option_ids,
            answer_text=payload.answer_text,
            duration_seconds=payload.duration_seconds,
        ),
    )


@router.post(
    "/{task_id}/questions/{task_question_id}/skip",
    response_model=StudyTaskAttemptResponse,
)
async def skip_study_task_question(
    task_id: Annotated[int, Path(gt=0)],
    task_question_id: Annotated[int, Path(gt=0)],
    payload: StudyTaskQuestionSkipRequest,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
) -> StudyTaskAttemptResponse:
    """跳过当前用户学习任务内的题目。"""

    return await pilot.learning.skip_study_task_question(
        user_id=current_user.id,
        task_id=task_id,
        task_question_id=task_question_id,
        payload=StudyTaskQuestionSkipCommand(duration_seconds=payload.duration_seconds),
    )
