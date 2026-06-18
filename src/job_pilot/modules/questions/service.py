from __future__ import annotations

import logging

from job_pilot.core.search import SearchBackend
from job_pilot.modules.questions.repository import QuestionRepository

logger = logging.getLogger(__name__)


class QuestionService:
    """岗位查询 service，负责查询编排和 ORM 到响应模型的转换。"""

    def __init__(
        self,
        repository: QuestionRepository,
    ) -> None:
        self.repository = repository


def build_question_service(search_backend: SearchBackend) -> QuestionService:
    """组装知识点树 service 的默认依赖。"""

    return QuestionService(
        repository=QuestionRepository(search_backend),
    )
