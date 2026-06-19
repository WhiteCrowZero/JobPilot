from __future__ import annotations

from enum import StrEnum


class StudyTaskStatus(StrEnum):
    """学习任务状态。"""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class StudyTaskType(StrEnum):
    """学习任务类型。"""

    SKILL_LEARNING = "skill_learning"
    QUESTION_PRACTICE = "question_practice"
    REVIEW = "review"


class StudyTaskSource(StrEnum):
    """学习任务来源。"""

    MATCH_MISSING_SKILL = "match_missing_skill"
    MATCH_WEAK_SKILL = "match_weak_skill"
    TARGET_SKILL_SUMMARY = "target_skill_summary"
    MANUAL = "manual"


class StudyTaskQuestionStatus(StrEnum):
    """学习任务内题目的当前状态。"""

    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"


class StudyTaskQuestionResult(StrEnum):
    """学习任务内题目的练习结果。"""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    SKIPPED = "skipped"
