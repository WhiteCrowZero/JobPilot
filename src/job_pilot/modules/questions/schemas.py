from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.modules.knowledge.enums import ContentSourceType
from job_pilot.modules.questions.contracts import QuestionSort
from job_pilot.modules.questions.enums import (
    QuestionDifficulty,
    QuestionSkillRelation,
    QuestionType,
)

PositiveId = Annotated[int, Field(gt=0)]


class QuestionSearchParams(PageParams):
    """题目搜索参数。

    用户侧只暴露学习所需筛选项，不暴露 archived、draft、rejected 等管理态。
    """

    keyword: str | None = Field(default=None, max_length=100)
    question_types: list[QuestionType] | None = Field(default=None, max_length=4)
    difficulties: list[QuestionDifficulty] | None = Field(default=None, max_length=3)
    source_types: list[ContentSourceType] | None = Field(default=None, max_length=2)
    skill_ids: list[PositiveId] | None = Field(default=None, max_length=50)
    knowledge_point_id: PositiveId | None = None
    sort: QuestionSort = "created_at_desc"


class QuestionSkillLinkResponse(BaseModel):
    """题目关联的技能和知识点。"""

    skill_id: int
    skill_name: str
    relation: QuestionSkillRelation
    knowledge_point_id: int | None = None
    knowledge_point_title: str | None = None


class QuestionListItem(BaseModel):
    """题目列表项，保留列表筛选和展示需要的字段。"""

    id: int
    title: str
    # TODO: 题库变大后改为 question_excerpt，完整题干只放详情响应。
    question_text: str
    question_type: QuestionType
    difficulty: QuestionDifficulty
    source_type: ContentSourceType
    primary_skill: QuestionSkillLinkResponse | None = None
    created_at: datetime
    updated_at: datetime


class QuestionListResponse(PageResult[QuestionListItem]):
    """题目分页列表响应。"""


class QuestionOptionResponse(BaseModel):
    """选择题选项响应。"""

    id: int
    option_label: str
    content: str
    is_correct: bool
    explanation: str | None = None
    sort_order: int


class QuestionAnswerResponse(BaseModel):
    """题目答案响应。

    官方答案唯一；多答案展示时 repository/service 应按 official 优先，再按创建时间排序。
    """

    id: int
    content: str
    source_type: ContentSourceType
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class QuestionDetailResponse(QuestionListItem):
    """题目详情响应，包含选项、答案和完整技能关联。"""

    source_note: str | None = None
    created_by_user_id: int | None = None
    options: list[QuestionOptionResponse] = Field(default_factory=list)
    answers: list[QuestionAnswerResponse] = Field(default_factory=list)
    skills: list[QuestionSkillLinkResponse] = Field(default_factory=list)
