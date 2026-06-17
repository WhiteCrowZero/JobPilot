from __future__ import annotations

from enum import StrEnum


class QuestionStatus(StrEnum):
    """题目状态。"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class QuestionReviewStatus(StrEnum):
    """题目审核状态。"""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class QuestionType(StrEnum):
    """题目类型。"""

    INTERVIEW_OPEN = "interview_open"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"


class QuestionDifficulty(StrEnum):
    """题目难度。"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionAnswerStatus(StrEnum):
    """题目答案状态。"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class QuestionSkillRelation(StrEnum):
    """题目和技能的关联角色。"""

    PRIMARY = "primary"
    RELATED = "related"
