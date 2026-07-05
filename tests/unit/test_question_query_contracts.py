from __future__ import annotations

import pytest
from pydantic import ValidationError

from job_pilot.modules.knowledge.enums import ContentSourceType
from job_pilot.modules.knowledge.schemas import KnowledgePointSearchParams
from job_pilot.modules.questions.contracts import QuestionSearchQuery
from job_pilot.modules.questions.enums import QuestionDifficulty, QuestionType
from job_pilot.modules.questions.schemas import QuestionSearchParams


def test_question_search_params_define_user_side_boundaries() -> None:
    """题目搜索参数只暴露用户侧需要的筛选边界。"""

    params = QuestionSearchParams(
        keyword="FastAPI",
        question_types=[QuestionType.INTERVIEW_OPEN],
        difficulties=[QuestionDifficulty.MEDIUM],
        source_types=[ContentSourceType.OFFICIAL],
        skill_ids=[1, 2],
        knowledge_point_id=10,
        sort="updated_at_desc",
        page=2,
        page_size=15,
    )
    query = QuestionSearchQuery(**params.model_dump())

    assert query.keyword == "FastAPI"
    assert query.question_types == [QuestionType.INTERVIEW_OPEN]
    assert query.difficulties == [QuestionDifficulty.MEDIUM]
    assert query.source_types == [ContentSourceType.OFFICIAL]
    assert query.skill_ids == [1, 2]
    assert query.knowledge_point_id == 10
    assert query.sort == "updated_at_desc"
    assert query.offset == 15
    assert query.limit == 15


def test_question_search_params_reject_invalid_boundaries() -> None:
    """题目搜索参数拒绝无效关键词长度和知识点 ID。"""

    with pytest.raises(ValidationError):
        QuestionSearchParams(keyword="x" * 101)

    with pytest.raises(ValidationError):
        QuestionSearchParams(knowledge_point_id=0)

    with pytest.raises(ValidationError):
        QuestionSearchParams(skill_ids=[1, 0])

    with pytest.raises(ValidationError):
        QuestionSearchParams(skill_ids=list(range(1, 52)))


def test_knowledge_point_search_params_use_stable_default_sort() -> None:
    """知识点搜索默认按更新时间倒序。"""

    params = KnowledgePointSearchParams()

    assert params.sort == "updated_at_desc"
