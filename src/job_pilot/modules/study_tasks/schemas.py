from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.modules.questions.enums import QuestionDifficulty, QuestionType
from job_pilot.modules.study_tasks.enums import (
    StudyTaskQuestionResult,
    StudyTaskQuestionStatus,
    StudyTaskSource,
    StudyTaskStatus,
    StudyTaskType,
)

PositiveId = Annotated[int, Field(gt=0)]


class StudyTaskGenerateFromTargetRequest(BaseModel):
    """从目标岗位生成学习任务请求。"""

    max_tasks: int = Field(default=3, ge=1, le=10)
    question_count_per_task: int = Field(default=5, ge=1, le=20)
    difficulty: QuestionDifficulty | None = None
    include_weak_skills: bool = True
    include_missing_skills: bool = True
    due_days: int | None = Field(default=7, ge=1, le=365)
    required_level: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def validate_gap_scope(self) -> Self:
        """至少选择一种技能缺口类型。"""

        if not self.include_weak_skills and not self.include_missing_skills:
            raise ValueError("include_weak_skills or include_missing_skills must be true")
        return self


class StudyTaskCreateRequest(BaseModel):
    """手动创建学习任务请求。"""

    skill_id: PositiveId
    task_type: StudyTaskType = StudyTaskType.QUESTION_PRACTICE
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    priority: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, gt=0)
    planned_start_date: date | None = None
    due_date: date | None = None
    question_ids: list[PositiveId] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_question_ids(self) -> Self:
        """手动绑定题目时不允许重复题目。"""

        if self.question_ids is not None and len(set(self.question_ids)) != len(self.question_ids):
            raise ValueError("question_ids must be unique")
        return self


class StudyTaskListParams(PageParams):
    """学习任务列表查询参数。"""

    statuses: list[StudyTaskStatus] | None = None
    skill_ids: list[PositiveId] | None = Field(default=None, max_length=50)


class StudyTaskUpdateRequest(BaseModel):
    """更新学习任务本体请求。"""

    status: StudyTaskStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    priority: int | None = Field(default=None, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, gt=0)
    actual_minutes: int | None = Field(default=None, ge=0)
    planned_start_date: date | None = None
    due_date: date | None = None


class StudyTaskQuestionAttemptRequest(BaseModel):
    """提交任务题目作答请求。"""

    selected_option_ids: list[PositiveId] | None = Field(default=None, max_length=20)
    answer_text: str | None = Field(default=None, min_length=1, max_length=4000)
    duration_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_answer_payload(self) -> Self:
        """选择题和开放题载荷不能混用，选项不能重复。"""

        has_selected_options = bool(self.selected_option_ids)
        has_answer_text = self.answer_text is not None
        if has_selected_options == has_answer_text:
            raise ValueError("selected_option_ids or answer_text is required")
        if self.selected_option_ids is not None and len(set(self.selected_option_ids)) != len(
            self.selected_option_ids
        ):
            raise ValueError("selected_option_ids must be unique")
        return self


class StudyTaskQuestionSkipRequest(BaseModel):
    """跳过任务内题目请求。"""

    duration_seconds: int | None = Field(default=None, ge=0)


class StudyTaskProgressResponse(BaseModel):
    """学习任务进度响应。"""

    total_question_count: int = Field(ge=0)
    completed_question_count: int = Field(ge=0)
    practiced_count: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    incorrect_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    progress_percent: Decimal = Field(ge=0, le=100)
    score: Decimal | None = Field(default=None, ge=0, le=100)
    last_practiced_at: datetime | None = None
    completed_at: datetime | None = None


class StudyTaskListItem(BaseModel):
    """学习任务列表项。"""

    id: int
    user_id: int
    skill_id: int
    skill_name: str
    source: StudyTaskSource
    source_key: str | None
    task_type: StudyTaskType
    status: StudyTaskStatus
    title: str
    description: str | None
    priority: int = Field(ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, gt=0)
    actual_minutes: int | None = Field(default=None, ge=0)
    planned_start_date: date | None
    due_date: date | None
    started_at: datetime | None
    completed_at: datetime | None
    archived_at: datetime | None
    progress: StudyTaskProgressResponse
    created_at: datetime
    updated_at: datetime


class StudyTaskListResponse(PageResult[StudyTaskListItem]):
    """学习任务分页响应。"""


class StudyTaskGenerationSkippedItem(BaseModel):
    """生成学习任务时跳过的技能及原因。"""

    skill_id: int
    skill_name: str
    reason: Literal["no_question", "already_exists", "difficulty_not_matched"]


class StudyTaskGenerationResponse(BaseModel):
    """从目标岗位生成学习任务响应。"""

    items: list[StudyTaskListItem]
    created_count: int = Field(ge=0)
    reused_count: int = Field(ge=0)
    skipped_skill_count: int = Field(ge=0)
    skipped_items: list[StudyTaskGenerationSkippedItem] = Field(default_factory=list)


class StudyTaskSnapshotResponse(BaseModel):
    """学习任务生成上下文快照响应。"""

    target_id: int | None
    job_post_id: int | None
    skill_name_snapshot: str
    job_title_snapshot: str | None
    company_name_snapshot: str | None
    target_title_snapshot: str | None
    match_status_snapshot: str | None
    required_level_snapshot: int | None = Field(default=None, ge=1, le=5)
    user_level_snapshot: int | None = Field(default=None, ge=1, le=5)
    is_primary_target_snapshot: bool | None
    target_priority_snapshot: int | None


class StudyTaskQuestionOptionResponse(BaseModel):
    """任务详情中可展示的题目选项，不暴露正确答案。"""

    id: int
    option_label: str
    content: str
    sort_order: int


class StudyTaskQuestionContentResponse(BaseModel):
    """任务详情中的题目正文。"""

    id: int
    title: str
    question_text: str
    question_type: QuestionType
    difficulty: QuestionDifficulty
    options: list[StudyTaskQuestionOptionResponse] = Field(default_factory=list)


class StudyTaskQuestionItem(BaseModel):
    """任务详情中的题目清单项。"""

    task_question_id: int
    question_id: int
    status: StudyTaskQuestionStatus
    last_result: StudyTaskQuestionResult | None
    last_score: Decimal | None = Field(default=None, ge=0, le=100)
    attempt_count: int = Field(ge=0)
    sort_order: int = Field(ge=0)
    assigned_at: datetime
    completed_at: datetime | None
    skipped_at: datetime | None
    question: StudyTaskQuestionContentResponse


class StudyTaskDetailResponse(StudyTaskListItem):
    """学习任务详情响应。"""

    snapshot: StudyTaskSnapshotResponse | None = None
    questions: list[StudyTaskQuestionItem] = Field(default_factory=list)


class StudyTaskQuestionAttemptStateResponse(BaseModel):
    """作答响应中的任务题目状态摘要。"""

    id: int
    task_id: int
    question_id: int
    status: StudyTaskQuestionStatus
    last_result: StudyTaskQuestionResult | None
    last_score: Decimal | None = Field(default=None, ge=0, le=100)
    attempt_count: int = Field(ge=0)
    completed_at: datetime | None
    skipped_at: datetime | None


class StudyTaskAttemptFeedbackResponse(BaseModel):
    """提交作答后的反馈响应。"""

    correct_option_ids: list[int] = Field(default_factory=list)
    explanation: str | None = None
    official_answer: str | None = None


class StudyTaskAttemptResponse(BaseModel):
    """提交任务题目作答响应。"""

    id: int
    task_id: int
    task_question_id: int
    question_id: int
    result: StudyTaskQuestionResult
    score: Decimal | None = Field(default=None, ge=0, le=100)
    selected_option_ids: list[int] | None
    answer_text: str | None
    duration_seconds: int | None
    attempted_at: datetime
    feedback: StudyTaskAttemptFeedbackResponse
    task_question: StudyTaskQuestionAttemptStateResponse
    progress: StudyTaskProgressResponse


class StudyTaskUpdateResponse(BaseModel):
    """更新学习任务本体后的响应。"""

    task_id: int
    user_id: int
    status: StudyTaskStatus
    title: str
    description: str | None
    priority: int = Field(ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, gt=0)
    actual_minutes: int | None = Field(default=None, ge=0)
    planned_start_date: date | None
    due_date: date | None
    started_at: datetime | None
    completed_at: datetime | None
    archived_at: datetime | None
    progress: StudyTaskProgressResponse
