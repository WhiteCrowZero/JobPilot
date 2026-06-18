from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.knowledge.enums import ContentSourceType, KnowledgePointLevel
from job_pilot.modules.knowledge.models import KnowledgePoint
from job_pilot.modules.questions.contracts import QuestionSearchQuery
from job_pilot.modules.questions.enums import (
    QuestionAnswerStatus,
    QuestionDifficulty,
    QuestionSkillRelation,
    QuestionType,
)
from job_pilot.modules.questions.models import (
    Question,
    QuestionAnswer,
    QuestionOption,
    QuestionSkill,
)
from tests.helpers.builders import seed_test_skill


@pytest.mark.asyncio
async def test_search_questions_returns_primary_skill_link(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """题目搜索返回主技能和知识点关联信息。"""

    await truncate_question_search_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        database = await seed_test_skill(db_session, "Database")
        generator = await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="生成器",
        )
        transaction = await seed_knowledge_point(
            db_session,
            skill_id=database.id,
            title="事务",
        )
        python_question = await seed_question(
            db_session,
            title="Python yield 原理",
            text="解释 yield 如何实现惰性迭代。",
        )
        database_question = await seed_question(
            db_session,
            title="数据库事务隔离",
            text="说明事务隔离级别。",
        )
        await seed_question_skill(
            db_session,
            question_id=python_question.id,
            skill_id=python.id,
            knowledge_point_id=generator.id,
            relation=QuestionSkillRelation.PRIMARY,
        )
        await seed_question_skill(
            db_session,
            question_id=database_question.id,
            skill_id=database.id,
            knowledge_point_id=transaction.id,
            relation=QuestionSkillRelation.PRIMARY,
        )

        result = await pilot.learning.search_questions(
            QuestionSearchQuery(
                skill_ids=[python.id],
                knowledge_point_id=generator.id,
                page=1,
                page_size=10,
            )
        )

        assert result.has_next is False
        assert [item.title for item in result.items] == ["Python yield 原理"]
        primary_skill = result.items[0].primary_skill
        assert primary_skill is not None
        assert primary_skill.skill_id == python.id
        assert primary_skill.skill_name == "Python"
        assert primary_skill.relation is QuestionSkillRelation.PRIMARY
        assert primary_skill.knowledge_point_id == generator.id
        assert primary_skill.knowledge_point_title == "生成器"
    finally:
        await truncate_question_search_tables(db_session)


@pytest.mark.asyncio
async def test_search_questions_requires_skill_and_knowledge_on_same_link(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """技能和知识点组合筛选必须命中同一条题目技能关系。"""

    await truncate_question_search_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        database = await seed_test_skill(db_session, "Database")
        generator = await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="生成器",
        )
        transaction = await seed_knowledge_point(
            db_session,
            skill_id=database.id,
            title="事务",
        )
        question = await seed_question(
            db_session,
            title="Python 与数据库综合题",
            text="说明 Python 生成器和数据库事务的区别。",
        )
        await seed_question_skill(
            db_session,
            question_id=question.id,
            skill_id=python.id,
            knowledge_point_id=generator.id,
            relation=QuestionSkillRelation.PRIMARY,
        )
        await seed_question_skill(
            db_session,
            question_id=question.id,
            skill_id=database.id,
            knowledge_point_id=transaction.id,
            relation=QuestionSkillRelation.RELATED,
        )

        result = await pilot.learning.search_questions(
            QuestionSearchQuery(
                skill_ids=[python.id],
                knowledge_point_id=transaction.id,
                page=1,
                page_size=10,
            )
        )

        assert result.items == []
    finally:
        await truncate_question_search_tables(db_session)


@pytest.mark.asyncio
async def test_get_question_detail_returns_loaded_relations_in_display_order(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """题目详情返回选项、答案和完整技能关联。"""

    await truncate_question_search_tables(db_session)
    try:
        python = await seed_test_skill(db_session, "Python")
        database = await seed_test_skill(db_session, "Database")
        generator = await seed_knowledge_point(
            db_session,
            skill_id=python.id,
            title="生成器",
        )
        transaction = await seed_knowledge_point(
            db_session,
            skill_id=database.id,
            title="事务",
        )
        question = await seed_question(
            db_session,
            title="Python yield 原理",
            text="解释 yield 如何实现惰性迭代。",
        )
        await seed_question_option(
            db_session,
            question_id=question.id,
            option_label="B",
            content="一次性计算全部结果",
            is_correct=False,
            sort_order=2,
        )
        await seed_question_option(
            db_session,
            question_id=question.id,
            option_label="A",
            content="暂停函数执行并在下次迭代时恢复",
            is_correct=True,
            sort_order=1,
        )
        await seed_question_answer(
            db_session,
            question_id=question.id,
            content="用户补充：yield 会返回一个生成器对象。",
            source_type=ContentSourceType.USER_SUPPLEMENT,
        )
        await seed_question_answer(
            db_session,
            question_id=question.id,
            content="官方答案：yield 让函数成为生成器，按需产出值。",
            source_type=ContentSourceType.OFFICIAL,
        )
        await seed_question_skill(
            db_session,
            question_id=question.id,
            skill_id=database.id,
            knowledge_point_id=transaction.id,
            relation=QuestionSkillRelation.RELATED,
        )
        await seed_question_skill(
            db_session,
            question_id=question.id,
            skill_id=python.id,
            knowledge_point_id=generator.id,
            relation=QuestionSkillRelation.PRIMARY,
        )

        detail = await pilot.learning.get_question_detail(question_id=question.id)

        assert detail.title == "Python yield 原理"
        assert [option.option_label for option in detail.options] == ["A", "B"]
        assert detail.options[0].is_correct is True
        assert [answer.source_type for answer in detail.answers] == [
            ContentSourceType.OFFICIAL,
            ContentSourceType.USER_SUPPLEMENT,
        ]
        assert detail.answers[0].content.startswith("官方答案")
        assert [skill.relation for skill in detail.skills] == [
            QuestionSkillRelation.PRIMARY,
            QuestionSkillRelation.RELATED,
        ]
        assert detail.skills[0].knowledge_point_title == "生成器"
    finally:
        await truncate_question_search_tables(db_session)


async def seed_knowledge_point(
    session: AsyncSession,
    *,
    skill_id: int,
    title: str,
) -> KnowledgePoint:
    """构造题目搜索所需的知识点。"""

    point = KnowledgePoint(
        skill_id=skill_id,
        title=title,
        level=KnowledgePointLevel.BASIC,
    )
    session.add(point)
    await session.commit()
    return point


async def seed_question(
    session: AsyncSession,
    *,
    title: str,
    text: str,
) -> Question:
    """构造 active + approved 测试题目。"""

    question = Question(
        title=title,
        question_text=text,
        question_hash=f"test-{title}",
        question_type=QuestionType.INTERVIEW_OPEN,
        difficulty=QuestionDifficulty.MEDIUM,
        source_type=ContentSourceType.OFFICIAL,
    )
    session.add(question)
    await session.commit()
    return question


async def seed_question_skill(
    session: AsyncSession,
    *,
    question_id: int,
    skill_id: int,
    knowledge_point_id: int,
    relation: QuestionSkillRelation,
) -> QuestionSkill:
    """构造题目和技能/知识点关系。"""

    question_skill = QuestionSkill(
        question_id=question_id,
        skill_id=skill_id,
        knowledge_point_id=knowledge_point_id,
        relation=relation,
    )
    session.add(question_skill)
    await session.commit()
    return question_skill


async def seed_question_option(
    session: AsyncSession,
    *,
    question_id: int,
    option_label: str,
    content: str,
    is_correct: bool,
    sort_order: int,
) -> QuestionOption:
    """构造题目详情所需的选项。"""

    option = QuestionOption(
        question_id=question_id,
        option_label=option_label,
        content=content,
        is_correct=is_correct,
        sort_order=sort_order,
    )
    session.add(option)
    await session.commit()
    return option


async def seed_question_answer(
    session: AsyncSession,
    *,
    question_id: int,
    content: str,
    source_type: ContentSourceType,
) -> QuestionAnswer:
    """构造题目详情所需的答案。"""

    answer = QuestionAnswer(
        question_id=question_id,
        content=content,
        source_type=source_type,
        status=QuestionAnswerStatus.ACTIVE,
    )
    session.add(answer)
    await session.commit()
    return answer


async def truncate_question_search_tables(session: AsyncSession) -> None:
    """清理题目搜索相关测试数据。"""

    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                question_skills,
                question_answers,
                question_options,
                questions,
                knowledge_points,
                skill_aliases,
                skills
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()
