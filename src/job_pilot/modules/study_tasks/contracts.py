from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from job_pilot.core.contracts import PageQuery
from job_pilot.modules.questions.enums import QuestionDifficulty
from job_pilot.modules.study_tasks.enums import (
    StudyTaskQuestionResult,
    StudyTaskQuestionStatus,
    StudyTaskStatus,
    StudyTaskType,
)

SkillGapStatus = Literal["missing", "weak"]


@dataclass(slots=True, frozen=True)
class StudyTaskGenerateFromTargetCommand:
    """从目标岗位生成学习任务的内部命令。"""

    max_tasks: int = 3
    question_count_per_task: int = 5
    difficulty: QuestionDifficulty | None = None
    include_weak_skills: bool = True
    include_missing_skills: bool = True
    due_days: int | None = 7
    required_level: int = 3


@dataclass(slots=True, frozen=True)
class StudyTaskCreateCommand:
    """手动创建学习任务的内部命令。"""

    skill_id: int
    title: str
    task_type: StudyTaskType = StudyTaskType.QUESTION_PRACTICE
    description: str | None = None
    priority: int = 3
    estimated_minutes: int | None = None
    planned_start_date: date | None = None
    due_date: date | None = None
    question_ids: list[int] | None = None


@dataclass(slots=True, frozen=True)
class StudyTaskListQuery(PageQuery):
    """学习任务列表内部查询参数。"""

    statuses: list[StudyTaskStatus] | None = None
    skill_ids: list[int] | None = None


@dataclass(slots=True, frozen=True)
class StudyTaskUpdateCommand:
    """更新学习任务本体元数据的内部命令。"""

    status: StudyTaskStatus | None = None
    title: str | None = None
    description: str | None = None
    priority: int | None = None
    estimated_minutes: int | None = None
    actual_minutes: int | None = None
    planned_start_date: date | None = None
    due_date: date | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class StudyTaskQuestionAttemptCommand:
    """提交任务题目作答的内部命令。"""

    selected_option_ids: list[int] | None = None
    answer_text: str | None = None
    duration_seconds: int | None = None


@dataclass(slots=True, frozen=True)
class StudyTaskQuestionSkipCommand:
    """跳过任务内题目的内部命令。"""

    duration_seconds: int | None = None


@dataclass(slots=True, frozen=True)
class StudyTaskProgressSnapshot:
    """作答动作后返回的任务进度快照。"""

    total_question_count: int
    completed_question_count: int
    practiced_count: int
    correct_count: int
    incorrect_count: int
    skipped_count: int
    progress_percent: Decimal
    score: Decimal | None = None
    last_practiced_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class StudyTaskGapCandidate:
    """目标岗位技能缺口候选项，后续由匹配分析和 repository 填充。"""

    target_id: int
    job_post_id: int
    skill_id: int
    skill_name: str
    match_status: SkillGapStatus
    required_level: int | None = None
    user_level: int | None = None
    job_title: str | None = None
    company_name: str | None = None
    target_title: str | None = None
    is_primary_target: bool | None = None
    target_priority: int | None = None


@dataclass(slots=True, frozen=True)
class StudyTaskQuestionCandidate:
    """生成任务时可挂载的题目候选项。"""

    question_id: int
    sort_order: int


@dataclass(slots=True, frozen=True)
class StudyTaskAttemptFeedback:
    """提交作答后的反馈信息。"""

    correct_option_ids: list[int]
    explanation: str | None = None
    official_answer: str | None = None


@dataclass(slots=True, frozen=True)
class StudyTaskAttemptMutationResult:
    """提交作答后一次事务内产生的聚合结果。"""

    attempt_id: int
    task_id: int
    task_question_id: int
    question_id: int
    result: StudyTaskQuestionResult
    score: Decimal | None
    selected_option_ids: list[int] | None
    answer_text: str | None
    duration_seconds: int | None
    attempted_at: datetime
    task_question_status: StudyTaskQuestionStatus
    task_question_last_result: StudyTaskQuestionResult | None
    task_question_last_score: Decimal | None
    task_question_attempt_count: int
    task_question_completed_at: datetime | None
    task_question_skipped_at: datetime | None
    feedback: StudyTaskAttemptFeedback
    progress: StudyTaskProgressSnapshot
