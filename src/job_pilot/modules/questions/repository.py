from __future__ import annotations

from typing import cast

from sqlalchemy import Select, and_, exists, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria
from sqlalchemy.sql.elements import ColumnElement

from job_pilot.core.search import (
    SearchBackend,
    SortMap,
    apply_sort_by_key,
    clean_optional_int_list,
    clean_optional_text,
    fetch_page_ids,
    order_entities_by_ids,
)
from job_pilot.modules.questions.contracts import QuestionSearchQuery
from job_pilot.modules.questions.enums import (
    QuestionAnswerStatus,
    QuestionReviewStatus,
    QuestionStatus,
)
from job_pilot.modules.questions.models import Question, QuestionAnswer, QuestionSkill

QUESTION_SORTS: SortMap = {
    "created_at_desc": lambda: cast(
        tuple[ColumnElement[object], ...],
        (Question.created_at.desc(), Question.id.desc()),
    ),
    "created_at_asc": lambda: cast(
        tuple[ColumnElement[object], ...],
        (Question.created_at.asc(), Question.id.asc()),
    ),
    "updated_at_desc": lambda: cast(
        tuple[ColumnElement[object], ...],
        (Question.updated_at.desc().nulls_last(), Question.id.desc()),
    ),
    "updated_at_asc": lambda: cast(
        tuple[ColumnElement[object], ...],
        (Question.updated_at.asc().nulls_last(), Question.id.asc()),
    ),
}


class QuestionRepository:
    """题目查询数据库操作。"""

    def __init__(self, search_backend: SearchBackend) -> None:
        self.search_backend = search_backend

    async def search_questions(
        self,
        *,
        db: AsyncSession,
        params: QuestionSearchQuery,
    ) -> list[Question]:
        """搜索 active + approved 题目列表，多取一条用于 has_next。"""

        base_stmt = self._build_base_search_stmt(params)
        stmt = self._apply_sort(base_stmt, params)
        question_ids = await fetch_page_ids(
            db,
            stmt,
            offset=params.offset,
            limit=params.limit,
        )
        if not question_ids:
            return []

        entity_stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(
                selectinload(Question.skill_links).selectinload(QuestionSkill.skill),
                selectinload(Question.skill_links).selectinload(QuestionSkill.knowledge_point),
            )
        )
        entity_result = await db.execute(entity_stmt)
        return order_entities_by_ids(
            question_ids, entity_result.scalars().all(), get_id=lambda question: question.id
        )

    async def get_question_detail(
        self,
        *,
        db: AsyncSession,
        question_id: int,
    ) -> Question | None:
        """读取 active + approved 题目详情。"""

        stmt = (
            select(Question)
            .where(
                Question.id == question_id,
                Question.status == QuestionStatus.ACTIVE,
                Question.review_status == QuestionReviewStatus.APPROVED,
            )
            .options(
                selectinload(Question.options),
                selectinload(Question.answers),
                selectinload(Question.skill_links).selectinload(QuestionSkill.skill),
                selectinload(Question.skill_links).selectinload(QuestionSkill.knowledge_point),
                with_loader_criteria(
                    QuestionAnswer,
                    QuestionAnswer.status == QuestionAnswerStatus.ACTIVE,
                ),
            )
        )
        question_entity = await db.execute(stmt)
        return question_entity.scalar_one_or_none()

    def _build_base_search_stmt(self, params: QuestionSearchQuery) -> Select[tuple[int]]:
        stmt = select(Question.id)

        conditions: list[ColumnElement[bool]] = []
        conditions.append(
            and_(
                Question.status == QuestionStatus.ACTIVE,
                Question.review_status == QuestionReviewStatus.APPROVED,
            )
        )
        skill_ids = clean_optional_int_list(params.skill_ids)
        if skill_ids and params.knowledge_point_id is not None:
            conditions.append(
                self._question_skill_exists(
                    skill_ids=skill_ids,
                    knowledge_point_id=params.knowledge_point_id,
                )
            )
        elif skill_ids:
            conditions.append(self._question_skill_exists(skill_ids=skill_ids))
        elif params.knowledge_point_id is not None:
            conditions.append(
                self._question_skill_exists(knowledge_point_id=params.knowledge_point_id)
            )

        if params.difficulties:
            conditions.append(Question.difficulty.in_(params.difficulties))
        if params.source_types:
            conditions.append(Question.source_type.in_(params.source_types))
        if params.question_types:
            conditions.append(Question.question_type.in_(params.question_types))

        keyword = clean_optional_text(params.keyword)
        if keyword is not None:
            conditions.append(
                self.search_backend.contains_text_in_any_field(
                    (
                        Question.title,
                        Question.question_text,
                    ),
                    keyword,
                )
            )

        if not conditions:
            return stmt
        return stmt.where(and_(*conditions))

    @staticmethod
    def _question_skill_exists(
        *,
        skill_ids: list[int] | None = None,
        knowledge_point_id: int | None = None,
    ) -> ColumnElement[bool]:
        """构造题目技能关系 exists，组合筛选必须命中同一条关系。"""

        relation_conditions: list[ColumnElement[bool]] = [
            QuestionSkill.question_id == Question.id,
        ]
        if skill_ids:
            relation_conditions.append(QuestionSkill.skill_id.in_(skill_ids))
        if knowledge_point_id is not None:
            relation_conditions.append(QuestionSkill.knowledge_point_id == knowledge_point_id)
        return exists(select(literal(1)).where(and_(*relation_conditions)))

    def _apply_sort(
        self,
        stmt: Select[tuple[int]],
        params: QuestionSearchQuery,
    ) -> Select[tuple[int]]:
        # 排序字段必须白名单控制，不允许前端直接传数据库字段名。
        return apply_sort_by_key(
            stmt,
            sort_key=params.sort,
            sort_map=QUESTION_SORTS,
            error_label="question",
        )
