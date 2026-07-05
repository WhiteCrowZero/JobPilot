from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.pagination import trim_page_items
from job_pilot.core.search import SearchBackend
from job_pilot.modules.knowledge.enums import ContentSourceType
from job_pilot.modules.questions.contracts import QuestionSearchQuery
from job_pilot.modules.questions.enums import QuestionSkillRelation
from job_pilot.modules.questions.exceptions import QuestionNotFoundError
from job_pilot.modules.questions.models import (
    Question,
    QuestionAnswer,
    QuestionOption,
    QuestionSkill,
)
from job_pilot.modules.questions.repository import QuestionRepository
from job_pilot.modules.questions.schemas import (
    QuestionAnswerResponse,
    QuestionDetailResponse,
    QuestionListItem,
    QuestionListResponse,
    QuestionOptionResponse,
    QuestionSkillLinkResponse,
)


class QuestionService:
    """题目查询 service。

    本阶段只固定 service 入口，具体 repository 调用和响应转换由后续实现补齐。
    """

    def __init__(
        self,
        repository: QuestionRepository,
    ) -> None:
        self.repository = repository

    async def search_questions(
        self,
        db: AsyncSession,
        *,
        params: QuestionSearchQuery,
    ) -> QuestionListResponse:
        """搜索题目列表。"""

        questions = await self.repository.search_questions(db=db, params=params)
        page_items, has_next = trim_page_items(
            questions,
            page_size=params.page_size,
        )
        return QuestionListResponse(
            items=[self._to_list_item(question) for question in page_items],
            page=params.page,
            page_size=params.page_size,
            total=None,
            has_next=has_next,
        )

    async def get_question_detail(
        self,
        db: AsyncSession,
        *,
        question_id: int,
    ) -> QuestionDetailResponse:
        """读取题目详情。"""

        question = await self.repository.get_question_detail(db=db, question_id=question_id)
        if question is None:
            raise QuestionNotFoundError()
        list_item = self._to_list_item(question)
        return QuestionDetailResponse(
            **list_item.model_dump(),
            source_note=question.source_note,
            created_by_user_id=question.created_by_user_id,
            options=[
                self._to_option_response(option)
                for option in sorted(
                    question.options,
                    key=lambda option: (option.sort_order, option.id),
                )
            ],
            answers=[
                self._to_answer_response(answer)
                for answer in sorted(
                    question.answers,
                    key=self._answer_sort_key,
                )
            ],
            skills=[
                self._to_skill_link_response(skill_link)
                for skill_link in sorted(
                    question.skill_links,
                    key=self._skill_link_sort_key,
                )
            ],
        )

    def _to_list_item(self, question: Question) -> QuestionListItem:
        return QuestionListItem(
            id=question.id,
            title=question.title,
            question_text=question.question_text,
            question_type=question.question_type,
            difficulty=question.difficulty,
            source_type=question.source_type,
            primary_skill=self._to_primary_skill(question),
            updated_at=question.updated_at,
            created_at=question.created_at,
        )

    def _to_primary_skill(self, question: Question) -> QuestionSkillLinkResponse | None:
        """从已预加载的关联里挑出主技能。"""

        primary_link = next(
            (
                skill_link
                for skill_link in question.skill_links
                if skill_link.relation is QuestionSkillRelation.PRIMARY
            ),
            None,
        )
        if primary_link is None:
            return None
        return self._to_skill_link_response(primary_link)

    @staticmethod
    def _to_skill_link_response(skill_link: QuestionSkill) -> QuestionSkillLinkResponse:
        return QuestionSkillLinkResponse(
            skill_id=skill_link.skill_id,
            skill_name=skill_link.skill.name,
            relation=skill_link.relation,
            knowledge_point_id=skill_link.knowledge_point_id,
            knowledge_point_title=(
                skill_link.knowledge_point.title if skill_link.knowledge_point is not None else None
            ),
        )

    @staticmethod
    def _to_option_response(option: QuestionOption) -> QuestionOptionResponse:
        return QuestionOptionResponse(
            id=option.id,
            option_label=option.option_label,
            content=option.content,
            is_correct=option.is_correct,
            explanation=option.explanation,
            sort_order=option.sort_order,
        )

    @staticmethod
    def _to_answer_response(answer: QuestionAnswer) -> QuestionAnswerResponse:
        return QuestionAnswerResponse(
            id=answer.id,
            content=answer.content,
            source_type=answer.source_type,
            created_by_user_id=answer.created_by_user_id,
            created_at=answer.created_at,
            updated_at=answer.updated_at,
        )

    @staticmethod
    def _answer_sort_key(answer: QuestionAnswer) -> tuple[int, float, int]:
        official_rank = 0 if answer.source_type is ContentSourceType.OFFICIAL else 1
        return (official_rank, -answer.created_at.timestamp(), -answer.id)

    @staticmethod
    def _skill_link_sort_key(skill_link: QuestionSkill) -> tuple[int, str, int]:
        primary_rank = 0 if skill_link.relation is QuestionSkillRelation.PRIMARY else 1
        return (primary_rank, skill_link.skill.name.lower(), skill_link.skill_id)


def build_question_service(search_backend: SearchBackend) -> QuestionService:
    """组装题目查询 service 的默认依赖。"""

    return QuestionService(
        repository=QuestionRepository(search_backend),
    )
