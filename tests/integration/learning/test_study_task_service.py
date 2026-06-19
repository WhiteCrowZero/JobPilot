from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.job_skills.models import Skill
from job_pilot.modules.questions.enums import QuestionSkillRelation, QuestionType
from job_pilot.modules.questions.models import Question, QuestionOption, QuestionSkill
from job_pilot.modules.study_tasks.contracts import (
    StudyTaskCreateCommand,
    StudyTaskGenerateFromTargetCommand,
    StudyTaskListQuery,
    StudyTaskQuestionAttemptCommand,
    StudyTaskQuestionSkipCommand,
    StudyTaskUpdateCommand,
)
from job_pilot.modules.study_tasks.enums import StudyTaskStatus, StudyTaskType
from job_pilot.modules.study_tasks.exceptions import (
    InvalidStudyTaskAnswerPayloadError,
    InvalidStudyTaskQuestionError,
    InvalidStudyTaskStatusTransitionError,
    StudyTaskNotFoundError,
    StudyTaskQuestionNotFoundError,
    StudyTaskSkillNotFoundError,
    StudyTaskTargetNotFoundError,
)
from job_pilot.modules.study_tasks.models import StudyTaskQuestionAttempt
from tests.helpers.builders import (
    create_test_user,
    seed_test_job_post,
    seed_test_job_post_skills,
    seed_test_skill,
    seed_test_target,
)
from tests.helpers.database import truncate_learning_tables


@pytest.mark.asyncio
async def test_create_manual_task_initializes_progress_and_hides_correct_answers(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """手动创建任务会初始化进度，详情响应不暴露正确答案字段。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        question, _options = await seed_choice_question(db_session, skill=skill)

        task = await pilot.learning.create_study_task(
            user_id=user.id,
            payload=StudyTaskCreateCommand(
                skill_id=skill.id,
                title="Python choice practice",
                question_ids=[question.id],
            ),
        )
        detail = await pilot.learning.get_study_task_detail(user_id=user.id, task_id=task.id)

        assert task.progress.total_question_count == 1
        assert task.progress.completed_question_count == 0
        assert task.progress.score is None
        assert detail.questions[0].question.options[0].id > 0
        assert "is_correct" not in str(detail.model_dump(mode="json"))
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_manual_task_rejects_invalid_skill_and_questions(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """手动创建任务应明确拒绝不存在的技能、无效题目和开放题。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        other_skill = await seed_test_skill(db_session, "Database")
        linked_to_other, _options = await seed_choice_question(db_session, skill=other_skill)
        open_question = await seed_open_question(db_session, skill=skill)

        with pytest.raises(StudyTaskSkillNotFoundError):
            await pilot.learning.create_study_task(
                user_id=user.id,
                payload=StudyTaskCreateCommand(
                    skill_id=999999,
                    title="Invalid skill",
                    question_ids=[linked_to_other.id],
                ),
            )
        with pytest.raises(InvalidStudyTaskQuestionError):
            await pilot.learning.create_study_task(
                user_id=user.id,
                payload=StudyTaskCreateCommand(
                    skill_id=skill.id,
                    title="Missing question",
                    question_ids=[999999],
                ),
            )
        with pytest.raises(InvalidStudyTaskQuestionError):
            await pilot.learning.create_study_task(
                user_id=user.id,
                payload=StudyTaskCreateCommand(
                    skill_id=skill.id,
                    title="Open question",
                    question_ids=[open_question.id],
                ),
            )
        with pytest.raises(InvalidStudyTaskQuestionError):
            await pilot.learning.create_study_task(
                user_id=user.id,
                payload=StudyTaskCreateCommand(
                    skill_id=skill.id,
                    title="Wrong skill link",
                    question_ids=[linked_to_other.id],
                ),
            )
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_question_practice_without_questions_is_rejected(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """question_practice 任务必须显式绑定题目。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")

        with pytest.raises(InvalidStudyTaskQuestionError):
            await pilot.learning.create_study_task(
                user_id=user.id,
                payload=StudyTaskCreateCommand(
                    skill_id=skill.id,
                    title="Empty practice",
                    question_ids=None,
                ),
            )

        review_task = await pilot.learning.create_study_task(
            user_id=user.id,
            payload=StudyTaskCreateCommand(
                skill_id=skill.id,
                title="Review notes",
                task_type=StudyTaskType.REVIEW,
                question_ids=None,
            ),
        )

        assert review_task.progress.total_question_count == 0
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_submit_correct_answer_updates_attempt_question_progress_and_completion(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """提交正确选择题会写 attempt、更新题目状态和完成任务。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        task_id, task_question_ids, option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=user.id,
            skill=skill,
            question_count=1,
        )

        response = await pilot.learning.submit_study_task_question_attempt(
            user_id=user.id,
            task_id=task_id,
            task_question_id=task_question_ids[0],
            payload=StudyTaskQuestionAttemptCommand(
                selected_option_ids=[option_groups[0][0].id],
                duration_seconds=12,
            ),
        )
        detail = await pilot.learning.get_study_task_detail(user_id=user.id, task_id=task_id)

        assert response.result == "correct"
        assert response.progress.correct_count == 1
        assert response.progress.score == Decimal("100.00")
        assert response.task_question.status == "done"
        assert detail.status == StudyTaskStatus.COMPLETED
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_submit_incorrect_answer_sets_score_to_zero(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """提交错误选择题会更新 incorrect_count 和 0 分。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        task_id, task_question_ids, option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=user.id,
            skill=skill,
            question_count=1,
        )

        response = await pilot.learning.submit_study_task_question_attempt(
            user_id=user.id,
            task_id=task_id,
            task_question_id=task_question_ids[0],
            payload=StudyTaskQuestionAttemptCommand(selected_option_ids=[option_groups[0][1].id]),
        )

        assert response.result == "incorrect"
        assert response.progress.incorrect_count == 1
        assert response.progress.score == Decimal("0.00")
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_skip_only_keeps_score_none_and_updates_progress_percent(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """只跳过题目时不计入得分分母，但会推进完成进度。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        task_id, task_question_ids, _option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=user.id,
            skill=skill,
            question_count=1,
        )

        response = await pilot.learning.skip_study_task_question(
            user_id=user.id,
            task_id=task_id,
            task_question_id=task_question_ids[0],
            payload=StudyTaskQuestionSkipCommand(duration_seconds=3),
        )

        assert response.result == "skipped"
        assert response.progress.skipped_count == 1
        assert response.progress.progress_percent == Decimal("100.00")
        assert response.progress.score is None
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_correct_and_incorrect_answers_result_in_half_score(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """一次正确加一次错误后，任务综合得分为 50。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        task_id, task_question_ids, option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=user.id,
            skill=skill,
            question_count=2,
        )

        await pilot.learning.submit_study_task_question_attempt(
            user_id=user.id,
            task_id=task_id,
            task_question_id=task_question_ids[0],
            payload=StudyTaskQuestionAttemptCommand(selected_option_ids=[option_groups[0][0].id]),
        )
        response = await pilot.learning.submit_study_task_question_attempt(
            user_id=user.id,
            task_id=task_id,
            task_question_id=task_question_ids[1],
            payload=StudyTaskQuestionAttemptCommand(selected_option_ids=[option_groups[1][1].id]),
        )

        assert response.progress.correct_count == 1
        assert response.progress.incorrect_count == 1
        assert response.progress.score == Decimal("50.00")
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_invalid_option_payload_does_not_create_attempt(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """非法选项 ID 或单选多选项请求不能写入 attempt。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        task_id, task_question_ids, option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=user.id,
            skill=skill,
            question_count=2,
        )

        invalid_payloads = [
            StudyTaskQuestionAttemptCommand(selected_option_ids=[999999]),
            StudyTaskQuestionAttemptCommand(selected_option_ids=[option_groups[1][0].id]),
            StudyTaskQuestionAttemptCommand(
                selected_option_ids=[option_groups[0][0].id, option_groups[0][1].id],
            ),
        ]
        for payload in invalid_payloads:
            with pytest.raises(InvalidStudyTaskAnswerPayloadError):
                await pilot.learning.submit_study_task_question_attempt(
                    user_id=user.id,
                    task_id=task_id,
                    task_question_id=task_question_ids[0],
                    payload=payload,
                )

        attempt_count = await db_session.scalar(select(func.count(StudyTaskQuestionAttempt.id)))
        assert attempt_count == 0
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_other_user_cannot_read_or_operate_task(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """非当前用户不能读取或操作其他用户的学习任务。"""

    await truncate_learning_tables(db_session)
    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other = await create_test_user(db_session, display_name="Other")
        skill = await seed_test_skill(db_session, "Python")
        task_id, task_question_ids, option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=owner.id,
            skill=skill,
            question_count=1,
        )

        with pytest.raises(StudyTaskNotFoundError):
            await pilot.learning.get_study_task_detail(user_id=other.id, task_id=task_id)
        with pytest.raises(StudyTaskQuestionNotFoundError):
            await pilot.learning.submit_study_task_question_attempt(
                user_id=other.id,
                task_id=task_id,
                task_question_id=task_question_ids[0],
                payload=StudyTaskQuestionAttemptCommand(
                    selected_option_ids=[option_groups[0][0].id],
                ),
            )
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_generate_from_missing_or_other_user_target_returns_not_found(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """生成学习任务前必须校验目标岗位存在且属于当前用户。"""

    await truncate_learning_tables(db_session)
    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other = await create_test_user(db_session, display_name="Other")
        skill = await seed_test_skill(db_session, "Python")
        job_post = await seed_test_job_post(db_session)
        await seed_test_job_post_skills(db_session, job_post_id=job_post.id, skill_ids=[skill.id])
        target = await seed_test_target(db_session, user_id=owner.id, job_post_id=job_post.id)

        with pytest.raises(StudyTaskTargetNotFoundError):
            await pilot.learning.generate_study_tasks_from_target(
                user_id=owner.id,
                target_id=999999,
                payload=StudyTaskGenerateFromTargetCommand(max_tasks=1),
            )
        with pytest.raises(StudyTaskTargetNotFoundError):
            await pilot.learning.generate_study_tasks_from_target(
                user_id=other.id,
                target_id=target.id,
                payload=StudyTaskGenerateFromTargetCommand(max_tasks=1),
            )
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_generate_skips_no_question_gap_and_continues_until_max_tasks(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """无可用题目的缺口进入 skipped_items，且不占用 max_tasks 名额。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        no_question_skill = await seed_test_skill(db_session, "A No Question")
        valid_skill = await seed_test_skill(db_session, "B Has Question")
        job_post = await seed_test_job_post(db_session)
        await seed_test_job_post_skills(
            db_session,
            job_post_id=job_post.id,
            skill_ids=[no_question_skill.id, valid_skill.id],
        )
        target = await seed_test_target(db_session, user_id=user.id, job_post_id=job_post.id)
        await seed_open_question(db_session, skill=no_question_skill)
        await seed_choice_question(db_session, skill=valid_skill)

        result = await pilot.learning.generate_study_tasks_from_target(
            user_id=user.id,
            target_id=target.id,
            payload=StudyTaskGenerateFromTargetCommand(max_tasks=1),
        )

        assert result.created_count == 1
        assert result.reused_count == 0
        assert result.skipped_skill_count == 1
        assert result.skipped_items[0].skill_id == no_question_skill.id
        assert result.skipped_items[0].reason == "no_question"
        assert result.items[0].skill_id == valid_skill.id
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_generated_task_is_idempotent_until_current_task_changes(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """同一目标技能缺口重复生成时应复用当前任务，避免重复生成。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        job_post = await seed_test_job_post(db_session)
        await seed_test_job_post_skills(db_session, job_post_id=job_post.id, skill_ids=[skill.id])
        target = await seed_test_target(db_session, user_id=user.id, job_post_id=job_post.id)
        await seed_choice_question(db_session, skill=skill)

        first = await pilot.learning.generate_study_tasks_from_target(
            user_id=user.id,
            target_id=target.id,
            payload=StudyTaskGenerateFromTargetCommand(max_tasks=1),
        )
        second = await pilot.learning.generate_study_tasks_from_target(
            user_id=user.id,
            target_id=target.id,
            payload=StudyTaskGenerateFromTargetCommand(max_tasks=1),
        )

        assert first.created_count == 1
        assert first.reused_count == 0
        assert second.created_count == 0
        assert second.reused_count == 1
        assert second.items[0].id == first.items[0].id
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_archived_task_is_hidden_from_default_list_but_visible_by_status(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """归档任务不进入默认待办列表，但显式查询 archived 可以看到。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        task_id, _task_question_ids, _option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=user.id,
            skill=skill,
            question_count=1,
        )

        before_archive = await pilot.learning.list_study_tasks(
            user_id=user.id,
            params=StudyTaskListQuery(),
        )
        await pilot.learning.archive_study_task(user_id=user.id, task_id=task_id)
        default_list = await pilot.learning.list_study_tasks(
            user_id=user.id,
            params=StudyTaskListQuery(),
        )
        archived_list = await pilot.learning.list_study_tasks(
            user_id=user.id,
            params=StudyTaskListQuery(statuses=[StudyTaskStatus.ARCHIVED]),
        )

        assert [item.id for item in before_archive.items] == [task_id]
        assert task_id not in [item.id for item in default_list.items]
        assert [item.id for item in archived_list.items] == [task_id]
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_completed_task_rejects_additional_attempts_and_skips(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """任务完成后不能继续提交或跳过题目，避免完成态被重复写入。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        task_id, task_question_ids, option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=user.id,
            skill=skill,
            question_count=1,
        )

        await pilot.learning.submit_study_task_question_attempt(
            user_id=user.id,
            task_id=task_id,
            task_question_id=task_question_ids[0],
            payload=StudyTaskQuestionAttemptCommand(
                selected_option_ids=[option_groups[0][0].id],
            ),
        )

        with pytest.raises(StudyTaskQuestionNotFoundError):
            await pilot.learning.submit_study_task_question_attempt(
                user_id=user.id,
                task_id=task_id,
                task_question_id=task_question_ids[0],
                payload=StudyTaskQuestionAttemptCommand(
                    selected_option_ids=[option_groups[0][0].id],
                ),
            )
        with pytest.raises(StudyTaskQuestionNotFoundError):
            await pilot.learning.skip_study_task_question(
                user_id=user.id,
                task_id=task_id,
                task_question_id=task_question_ids[0],
                payload=StudyTaskQuestionSkipCommand(),
            )

        attempt_count = await db_session.scalar(select(func.count(StudyTaskQuestionAttempt.id)))
        assert attempt_count == 1
    finally:
        await truncate_learning_tables(db_session)


@pytest.mark.asyncio
async def test_update_task_status_transition_rules(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """学习任务状态只能按 MVP 允许的方向流转。"""

    await truncate_learning_tables(db_session)
    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")
        task_id, _task_question_ids, _option_groups = await create_practice_task(
            pilot,
            db_session,
            user_id=user.id,
            skill=skill,
            question_count=1,
        )

        in_progress = await pilot.learning.update_study_task(
            user_id=user.id,
            task_id=task_id,
            payload=StudyTaskUpdateCommand(
                status=StudyTaskStatus.IN_PROGRESS,
                fields_set=frozenset({"status"}),
            ),
        )
        completed = await pilot.learning.update_study_task(
            user_id=user.id,
            task_id=task_id,
            payload=StudyTaskUpdateCommand(
                status=StudyTaskStatus.COMPLETED,
                fields_set=frozenset({"status"}),
            ),
        )

        with pytest.raises(InvalidStudyTaskStatusTransitionError):
            await pilot.learning.update_study_task(
                user_id=user.id,
                task_id=task_id,
                payload=StudyTaskUpdateCommand(
                    status=StudyTaskStatus.TODO,
                    fields_set=frozenset({"status"}),
                ),
            )

        archived = await pilot.learning.archive_study_task(user_id=user.id, task_id=task_id)
        with pytest.raises(InvalidStudyTaskStatusTransitionError):
            await pilot.learning.update_study_task(
                user_id=user.id,
                task_id=task_id,
                payload=StudyTaskUpdateCommand(
                    status=StudyTaskStatus.IN_PROGRESS,
                    fields_set=frozenset({"status"}),
                ),
            )

        assert in_progress.status == StudyTaskStatus.IN_PROGRESS
        assert completed.status == StudyTaskStatus.COMPLETED
        assert archived.status == StudyTaskStatus.ARCHIVED
    finally:
        await truncate_learning_tables(db_session)


async def create_practice_task(
    pilot: JobPilot,
    session: AsyncSession,
    *,
    user_id: int,
    skill: Skill,
    question_count: int,
) -> tuple[int, list[int], list[list[QuestionOption]]]:
    """创建带单选题的练习任务，并返回任务题目和选项。"""

    questions: list[Question] = []
    option_groups: list[list[QuestionOption]] = []
    for index in range(question_count):
        question, options = await seed_choice_question(
            session,
            skill=skill,
            title=f"Python question {index}",
        )
        questions.append(question)
        option_groups.append(options)

    task = await pilot.learning.create_study_task(
        user_id=user_id,
        payload=StudyTaskCreateCommand(
            skill_id=skill.id,
            title="Practice Python",
            question_ids=[question.id for question in questions],
        ),
    )
    detail = await pilot.learning.get_study_task_detail(user_id=user_id, task_id=task.id)
    return (
        task.id,
        [item.task_question_id for item in detail.questions],
        option_groups,
    )


async def seed_choice_question(
    session: AsyncSession,
    *,
    skill: Skill,
    title: str = "Python basics",
) -> tuple[Question, list[QuestionOption]]:
    """创建一题可自动判分的单选题。"""

    question = Question(
        title=title,
        question_text=f"{title} text {uuid4().hex}",
        question_hash=uuid4().hex,
        question_type=QuestionType.SINGLE_CHOICE,
    )
    session.add(question)
    await session.flush()

    session.add(
        QuestionSkill(
            question_id=question.id,
            skill_id=skill.id,
            relation=QuestionSkillRelation.PRIMARY,
        )
    )
    options = [
        QuestionOption(
            question_id=question.id,
            option_label="A",
            content="Correct",
            is_correct=True,
            explanation="Correct option",
            sort_order=1,
        ),
        QuestionOption(
            question_id=question.id,
            option_label="B",
            content="Wrong",
            is_correct=False,
            sort_order=2,
        ),
    ]
    session.add_all(options)
    await session.commit()
    return question, options


async def seed_open_question(
    session: AsyncSession,
    *,
    skill: Skill,
) -> Question:
    """创建开放面试题，用于校验不进入自动练习。"""

    question = Question(
        title="Open interview question",
        question_text=f"Explain Python {uuid4().hex}",
        question_hash=uuid4().hex,
        question_type=QuestionType.INTERVIEW_OPEN,
    )
    session.add(question)
    await session.flush()
    session.add(
        QuestionSkill(
            question_id=question.id,
            skill_id=skill.id,
            relation=QuestionSkillRelation.PRIMARY,
        )
    )
    await session.commit()
    return question
