from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from job_pilot.core.contracts import PageQuery
from job_pilot.modules.knowledge.enums import ContentSourceType
from job_pilot.modules.questions.enums import QuestionDifficulty, QuestionType

QuestionSort = Literal[
    "created_at_desc",
    "created_at_asc",
    "updated_at_desc",
    "updated_at_asc",
]


@dataclass(slots=True, frozen=True)
class QuestionSearchQuery(PageQuery):
    """题目搜索内部查询参数。

    普通用户入口固定只查询 active + approved 题目，归档和审核状态后续留给 admin API。
    """

    keyword: str | None = None
    question_types: list[QuestionType] | None = None
    difficulties: list[QuestionDifficulty] | None = None
    source_types: list[ContentSourceType] | None = None
    skill_ids: list[int] | None = None
    knowledge_point_id: int | None = None
    sort: QuestionSort = "created_at_desc"
