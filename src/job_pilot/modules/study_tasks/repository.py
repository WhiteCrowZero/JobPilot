from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from job_pilot.core.search import fetch_offset_page
from job_pilot.modules.job_posts.models import JobPost, JobSource
from job_pilot.modules.job_skills.models import JobPostSkill, Skill
from job_pilot.modules.job_targets.models import JobTarget
from job_pilot.modules.job_targets.policies import CURRENT_TARGET_STATUSES
from job_pilot.modules.knowledge.enums import ContentSourceType
from job_pilot.modules.questions.enums import (
    QuestionAnswerStatus,
    QuestionDifficulty,
    QuestionReviewStatus,
    QuestionSkillRelation,
    QuestionStatus,
    QuestionType,
)
from job_pilot.modules.questions.models import (
    Question,
    QuestionAnswer,
    QuestionOption,
    QuestionSkill,
)
from job_pilot.modules.study_tasks.contracts import (
    StudyTaskAttemptFeedback,
    StudyTaskAttemptMutationResult,
    StudyTaskCreateCommand,
    StudyTaskGapCandidate,
    StudyTaskGenerateFromTargetCommand,
    StudyTaskListQuery,
    StudyTaskProgressSnapshot,
    StudyTaskQuestionAttemptCommand,
    StudyTaskQuestionCandidate,
    StudyTaskQuestionSkipCommand,
    StudyTaskUpdateCommand,
)
from job_pilot.modules.study_tasks.enums import (
    StudyTaskQuestionResult,
    StudyTaskQuestionStatus,
    StudyTaskSource,
    StudyTaskStatus,
    StudyTaskType,
)
from job_pilot.modules.study_tasks.exceptions import (
    InvalidStudyTaskAnswerPayloadError,
    InvalidStudyTaskQuestionError,
    InvalidStudyTaskStatusTransitionError,
    StudyTaskQuestionTypeNotSupportedError,
    StudyTaskSkillNotFoundError,
)
from job_pilot.modules.study_tasks.models import (
    StudyTask,
    StudyTaskProgress,
    StudyTaskQuestion,
    StudyTaskQuestionAttempt,
    StudyTaskSnapshot,
)
from job_pilot.modules.user_skills.enums import UserSkillStatus
from job_pilot.modules.user_skills.models import UserSkill


@dataclass(slots=True, frozen=True)
class _AttemptGradeResult:
    """题目作答判定结果。"""

    result: StudyTaskQuestionResult
    score: Decimal | None
    feedback: StudyTaskAttemptFeedback


AUTO_GRADABLE_QUESTION_TYPES: tuple[QuestionType, QuestionType, QuestionType] = (
    QuestionType.SINGLE_CHOICE,
    QuestionType.MULTIPLE_CHOICE,
    QuestionType.TRUE_FALSE,
)


class StudyTaskRepository:
    """学习任务数据库操作。

    封装学习任务生成、手动创建、作答和进度更新所需的 SQL。
    """

    async def get_current_target_for_generation(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
    ) -> JobTarget | None:
        """读取当前用户可用于生成学习任务的目标岗位。"""

        stmt = select(JobTarget).where(
            JobTarget.user_id == user_id,
            JobTarget.id == target_id,
            JobTarget.status.in_(CURRENT_TARGET_STATUSES),
        )
        return await db.scalar(stmt)

    async def list_target_skill_gaps(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        required_level: int,
    ) -> list[StudyTaskGapCandidate]:
        """查询目标岗位的 missing/weak 技能缺口候选项。"""

        match_status = case(
            (UserSkill.id.is_(None), "missing"),
            else_="weak",
        ).label("match_status")
        stmt = (
            select(
                JobTarget.id,
                JobTarget.job_post_id,
                JobTarget.priority,
                JobTarget.is_primary,
                JobPost.title,
                JobSource.name,
                Skill.id,
                Skill.name,
                UserSkill.proficiency_level,
                match_status,
            )
            .join(JobPost, JobPost.id == JobTarget.job_post_id)
            .join(JobSource, JobSource.id == JobPost.source_id)
            .join(JobPostSkill, JobPostSkill.job_post_id == JobTarget.job_post_id)
            .join(Skill, Skill.id == JobPostSkill.skill_id)
            .outerjoin(
                UserSkill,
                and_(
                    UserSkill.user_id == user_id,
                    UserSkill.skill_id == Skill.id,
                    UserSkill.status == UserSkillStatus.ACTIVE,
                ),
            )
            .where(
                JobTarget.user_id == user_id,
                JobTarget.id == target_id,
                JobTarget.status.in_(CURRENT_TARGET_STATUSES),
                JobPost.deleted_at.is_(None),
                or_(
                    UserSkill.id.is_(None),
                    UserSkill.proficiency_level < required_level,
                ),
            )
            .order_by(match_status.asc(), Skill.name.asc(), Skill.id.asc())
        )
        result = await db.execute(stmt)
        return [
            StudyTaskGapCandidate(
                target_id=target_id_value,
                job_post_id=job_post_id,
                skill_id=skill_id,
                skill_name=skill_name,
                match_status=match_status_value,
                required_level=required_level,
                user_level=user_level,
                job_title=job_title,
                company_name=company_name,
                target_title=job_title,
                is_primary_target=is_primary,
                target_priority=target_priority,
            )
            for (
                target_id_value,
                job_post_id,
                target_priority,
                is_primary,
                job_title,
                company_name,
                skill_id,
                skill_name,
                user_level,
                match_status_value,
            ) in result.all()
        ]

    async def list_question_candidates_for_skill(
        self,
        db: AsyncSession,
        *,
        skill_id: int,
        limit: int,
        difficulty: QuestionDifficulty | None,
    ) -> list[StudyTaskQuestionCandidate]:
        """查询某个技能可加入任务的题目候选项。"""

        stmt = (
            select(Question.id)
            .join(QuestionSkill, QuestionSkill.question_id == Question.id)
            .where(
                QuestionSkill.skill_id == skill_id,
                Question.status == QuestionStatus.ACTIVE,
                Question.review_status == QuestionReviewStatus.APPROVED,
                Question.question_type.in_(AUTO_GRADABLE_QUESTION_TYPES),
            )
            .order_by(
                case(
                    (QuestionSkill.relation == QuestionSkillRelation.PRIMARY, 0),
                    else_=1,
                ).asc(),
                Question.difficulty.asc(),
                Question.created_at.desc(),
                Question.id.desc(),
            )
        )
        if difficulty is not None:
            stmt = stmt.where(Question.difficulty == difficulty)
        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return [
            StudyTaskQuestionCandidate(
                question_id=question_id,
                sort_order=sort_order,
            )
            for sort_order, question_id in enumerate(result.scalars().all(), start=1)
        ]

    async def create_or_reuse_generated_task(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        gap: StudyTaskGapCandidate,
        question_candidates: list[StudyTaskQuestionCandidate],
        command: StudyTaskGenerateFromTargetCommand,
    ) -> tuple[StudyTask, bool]:
        """按 source_key 幂等创建或复用学习任务。

        返回值第二项表示是否新建，True 为 created，False 为 reused。
        """

        source_key = self._build_generated_source_key(gap)
        existed_task = await self._get_current_task_by_source_key(
            db,
            user_id=user_id,
            source_key=source_key,
        )
        if existed_task is not None:
            return existed_task, False

        due_date = (
            date.today() + timedelta(days=command.due_days)
            if command.due_days is not None
            else None
        )
        task = StudyTask(
            user_id=user_id,
            skill_id=gap.skill_id,
            source=self._source_from_gap_status(gap.match_status),
            source_key=source_key,
            task_type=StudyTaskType.QUESTION_PRACTICE,
            status=StudyTaskStatus.TODO,
            title=f"练习 {gap.skill_name} 面试题",
            description=self._build_generated_description(gap),
            priority=gap.target_priority or 3,
            estimated_minutes=len(question_candidates) * 10,
            due_date=due_date,
        )
        db.add(task)
        await db.flush()

        db.add(
            StudyTaskSnapshot(
                study_task_id=task.id,
                target_id=gap.target_id,
                job_post_id=gap.job_post_id,
                skill_name_snapshot=gap.skill_name,
                job_title_snapshot=gap.job_title,
                company_name_snapshot=gap.company_name,
                target_title_snapshot=gap.target_title,
                match_status_snapshot=gap.match_status,
                required_level_snapshot=gap.required_level,
                user_level_snapshot=gap.user_level,
                is_primary_target_snapshot=gap.is_primary_target,
                target_priority_snapshot=gap.target_priority,
            )
        )
        self._add_progress(
            db,
            user_id=user_id,
            task_id=task.id,
            total_question_count=len(question_candidates),
        )
        self._add_task_questions(
            db,
            task_id=task.id,
            question_candidates=question_candidates,
        )
        await db.flush()

        created_task = await self._get_task_for_response(db, user_id=user_id, task_id=task.id)
        if created_task is None:
            raise RuntimeError("Created study task cannot be loaded")
        return created_task, True

    async def create_user_task(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        payload: StudyTaskCreateCommand,
    ) -> StudyTask:
        """手动创建当前用户学习任务。"""

        skill = await db.get(Skill, payload.skill_id)
        if skill is None:
            raise StudyTaskSkillNotFoundError()

        question_candidates = await self._build_manual_question_candidates(
            db,
            skill_id=payload.skill_id,
            task_type=payload.task_type,
            question_ids=payload.question_ids,
        )

        task = StudyTask(
            user_id=user_id,
            skill_id=payload.skill_id,
            source=StudyTaskSource.MANUAL,
            source_key=None,
            task_type=payload.task_type,
            status=StudyTaskStatus.TODO,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            estimated_minutes=payload.estimated_minutes,
            planned_start_date=payload.planned_start_date,
            due_date=payload.due_date,
        )
        db.add(task)
        await db.flush()

        self._add_progress(
            db,
            user_id=user_id,
            task_id=task.id,
            total_question_count=len(question_candidates),
        )
        self._add_task_questions(
            db,
            task_id=task.id,
            question_candidates=question_candidates,
        )
        await db.flush()

        created_task = await self._get_task_for_response(db, user_id=user_id, task_id=task.id)
        if created_task is None:
            raise RuntimeError("Created study task cannot be loaded")
        return created_task

    async def list_user_tasks(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: StudyTaskListQuery,
    ) -> list[StudyTask]:
        """分页查询当前用户学习任务。"""

        conditions: list[ColumnElement[bool]] = [StudyTask.user_id == user_id]
        if params.skill_ids:
            conditions.append(StudyTask.skill_id.in_(params.skill_ids))

        if params.statuses:
            conditions.append(StudyTask.status.in_(params.statuses))
        else:
            conditions.append(
                StudyTask.status.in_((StudyTaskStatus.TODO, StudyTaskStatus.IN_PROGRESS))
            )

        stmt = (
            select(StudyTask)
            .where(*conditions)
            .order_by(
                StudyTask.priority.asc(),
                StudyTask.due_date.asc().nulls_last(),
                StudyTask.created_at.desc(),
                StudyTask.id.desc(),
            )
            .options(
                selectinload(StudyTask.skill),
                selectinload(StudyTask.progress),
            )
        )
        return await fetch_offset_page(
            db,
            stmt,
            offset=params.offset,
            limit=params.limit,
        )

    async def get_user_task_detail(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
    ) -> StudyTask | None:
        """读取当前用户学习任务详情。"""

        stmt = (
            select(StudyTask)
            .where(
                StudyTask.user_id == user_id,
                StudyTask.id == task_id,
            )
            .options(
                selectinload(StudyTask.skill),
                selectinload(StudyTask.progress),
                selectinload(StudyTask.snapshot),
                selectinload(StudyTask.questions)
                .selectinload(StudyTaskQuestion.question)
                .selectinload(Question.options),
            )
        )
        entity_result = await db.execute(stmt)
        return entity_result.scalar_one_or_none()

    async def submit_question_attempt(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        task_question_id: int,
        payload: StudyTaskQuestionAttemptCommand,
    ) -> StudyTaskAttemptMutationResult | None:
        """提交一次题目作答，并在同一事务内更新题目状态和任务进度。"""

        task_question = await self._get_task_question_for_mutation(
            db,
            user_id=user_id,
            task_id=task_id,
            task_question_id=task_question_id,
        )
        if task_question is None:
            return None

        answer_result = await self._grade_attempt(
            db,
            question_id=task_question.question_id,
            payload=payload,
        )
        return await self._record_question_attempt(
            db,
            user_id=user_id,
            task_question=task_question,
            result=answer_result.result,
            score=answer_result.score,
            selected_option_ids=payload.selected_option_ids,
            answer_text=payload.answer_text,
            duration_seconds=payload.duration_seconds,
            feedback=answer_result.feedback,
        )

    async def update_task_metadata(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        payload: StudyTaskUpdateCommand,
    ) -> StudyTask | None:
        """更新当前用户学习任务本体元数据。"""

        task = await self._get_task_for_update(db, user_id=user_id, task_id=task_id)
        if task is None:
            return None

        if "title" in payload.fields_set:
            task.title = payload.title or task.title
        if "description" in payload.fields_set:
            task.description = payload.description
        if "priority" in payload.fields_set and payload.priority is not None:
            task.priority = payload.priority
        if "estimated_minutes" in payload.fields_set:
            task.estimated_minutes = payload.estimated_minutes
        if "actual_minutes" in payload.fields_set:
            task.actual_minutes = payload.actual_minutes
        if "planned_start_date" in payload.fields_set:
            task.planned_start_date = payload.planned_start_date
        if "due_date" in payload.fields_set:
            task.due_date = payload.due_date
        if "status" in payload.fields_set and payload.status is not None:
            self._validate_task_status_transition(task.status, payload.status)
            self._apply_task_status(task, status=payload.status)

        task.updated_at = datetime.now(UTC)
        await db.flush()
        return await self._get_task_for_response(db, user_id=user_id, task_id=task.id)

    async def archive_user_task(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
    ) -> StudyTask | None:
        """归档当前用户学习任务。"""

        task = await self._get_task_for_update(db, user_id=user_id, task_id=task_id)
        if task is None:
            return None

        self._apply_task_status(task, status=StudyTaskStatus.ARCHIVED)
        task.updated_at = datetime.now(UTC)
        await db.flush()
        return await self._get_task_for_response(db, user_id=user_id, task_id=task.id)

    async def skip_task_question(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        task_question_id: int,
        payload: StudyTaskQuestionSkipCommand,
    ) -> StudyTaskAttemptMutationResult | None:
        """跳过任务题目，并在同一事务内更新题目状态和任务进度。"""

        task_question = await self._get_task_question_for_mutation(
            db,
            user_id=user_id,
            task_id=task_id,
            task_question_id=task_question_id,
        )
        if task_question is None:
            return None

        return await self._record_question_attempt(
            db,
            user_id=user_id,
            task_question=task_question,
            result=StudyTaskQuestionResult.SKIPPED,
            score=None,
            selected_option_ids=None,
            answer_text=None,
            duration_seconds=payload.duration_seconds,
            feedback=StudyTaskAttemptFeedback(
                correct_option_ids=[],
                explanation=None,
                official_answer=None,
            ),
        )

    async def _record_question_attempt(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_question: StudyTaskQuestion,
        result: StudyTaskQuestionResult,
        score: Decimal | None,
        selected_option_ids: list[int] | None,
        answer_text: str | None,
        duration_seconds: int | None,
        feedback: StudyTaskAttemptFeedback,
    ) -> StudyTaskAttemptMutationResult:
        """记录一次题目动作并同步任务进度。"""

        task = task_question.study_task
        now = datetime.now(UTC)

        task_question.status = (
            StudyTaskQuestionStatus.SKIPPED
            if result == StudyTaskQuestionResult.SKIPPED
            else StudyTaskQuestionStatus.DONE
        )
        task_question.last_result = result
        task_question.last_score = score
        task_question.attempt_count += 1
        task_question.last_practiced_at = now
        task_question.completed_at = None if result == StudyTaskQuestionResult.SKIPPED else now
        task_question.skipped_at = now if result == StudyTaskQuestionResult.SKIPPED else None
        task_question.updated_at = now

        if task.started_at is None:
            task.started_at = now
        if task.status == StudyTaskStatus.TODO:
            task.status = StudyTaskStatus.IN_PROGRESS
        task.updated_at = now

        attempt = StudyTaskQuestionAttempt(
            user_id=user_id,
            study_task_id=task.id,
            study_task_question_id=task_question.id,
            question_id=task_question.question_id,
            result=result,
            score=score,
            selected_option_ids=selected_option_ids,
            answer_text=answer_text,
            duration_seconds=duration_seconds,
            attempted_at=now,
        )
        db.add(attempt)
        await db.flush()

        progress = await self._get_or_create_progress(
            db,
            user_id=user_id,
            task_id=task.id,
        )
        total_question_count = await self._count_task_questions(db, task_id=task.id)
        completed_question_count = await self._count_completed_task_questions(
            db,
            task_id=task.id,
        )
        progress_percent = self._calculate_progress_percent(
            completed_question_count=completed_question_count,
            total_question_count=total_question_count,
        )
        is_task_completed = total_question_count > 0 and (
            completed_question_count >= total_question_count
        )

        progress.total_question_count = total_question_count
        progress.completed_question_count = completed_question_count
        progress.practiced_count += 1
        if result == StudyTaskQuestionResult.CORRECT:
            progress.correct_count += 1
        elif result == StudyTaskQuestionResult.INCORRECT:
            progress.incorrect_count += 1
        else:
            progress.skipped_count += 1
        progress.progress_percent = progress_percent
        progress.score = self._calculate_score(
            correct_count=progress.correct_count,
            incorrect_count=progress.incorrect_count,
        )
        progress.last_practiced_at = now
        progress.completed_at = now if is_task_completed else None
        progress.updated_at = now

        if is_task_completed:
            task.status = StudyTaskStatus.COMPLETED
            task.completed_at = now

        return StudyTaskAttemptMutationResult(
            attempt_id=attempt.id,
            task_id=task.id,
            task_question_id=task_question.id,
            question_id=task_question.question_id,
            result=result,
            score=score,
            selected_option_ids=selected_option_ids,
            answer_text=answer_text,
            duration_seconds=duration_seconds,
            attempted_at=now,
            task_question_status=task_question.status,
            task_question_last_result=task_question.last_result,
            task_question_last_score=task_question.last_score,
            task_question_attempt_count=task_question.attempt_count,
            task_question_completed_at=task_question.completed_at,
            task_question_skipped_at=task_question.skipped_at,
            feedback=feedback,
            progress=StudyTaskProgressSnapshot(
                total_question_count=progress.total_question_count,
                completed_question_count=progress.completed_question_count,
                practiced_count=progress.practiced_count,
                correct_count=progress.correct_count,
                incorrect_count=progress.incorrect_count,
                skipped_count=progress.skipped_count,
                progress_percent=progress.progress_percent,
                score=progress.score,
                last_practiced_at=progress.last_practiced_at,
                completed_at=progress.completed_at,
            ),
        )

    async def _get_current_task_by_source_key(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        source_key: str,
    ) -> StudyTask | None:
        """按幂等键读取当前未完成的生成任务。"""

        stmt = (
            select(StudyTask)
            .where(
                StudyTask.user_id == user_id,
                StudyTask.source_key == source_key,
                StudyTask.status.in_((StudyTaskStatus.TODO, StudyTaskStatus.IN_PROGRESS)),
            )
            .options(
                selectinload(StudyTask.skill),
                selectinload(StudyTask.progress),
            )
        )
        return await db.scalar(stmt)

    async def _get_task_for_response(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
    ) -> StudyTask | None:
        """读取用于列表/更新响应的任务聚合。"""

        stmt = (
            select(StudyTask)
            .where(
                StudyTask.user_id == user_id,
                StudyTask.id == task_id,
            )
            .options(
                selectinload(StudyTask.skill),
                selectinload(StudyTask.progress),
            )
        )
        return await db.scalar(stmt)

    async def _get_task_for_update(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
    ) -> StudyTask | None:
        """读取并锁定当前用户任务。"""

        stmt = (
            select(StudyTask)
            .where(
                StudyTask.user_id == user_id,
                StudyTask.id == task_id,
            )
            .with_for_update()
        )
        return await db.scalar(stmt)

    async def _get_task_question_for_mutation(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        task_question_id: int,
    ) -> StudyTaskQuestion | None:
        """读取并锁定当前用户任务内的题目。"""

        stmt = (
            select(StudyTaskQuestion)
            .join(StudyTask, StudyTask.id == StudyTaskQuestion.study_task_id)
            .where(
                StudyTaskQuestion.id == task_question_id,
                StudyTaskQuestion.study_task_id == task_id,
                StudyTask.user_id == user_id,
                StudyTask.status.in_((StudyTaskStatus.TODO, StudyTaskStatus.IN_PROGRESS)),
            )
            .options(selectinload(StudyTaskQuestion.study_task))
            .with_for_update()
        )
        return await db.scalar(stmt)

    async def _build_manual_question_candidates(
        self,
        db: AsyncSession,
        *,
        skill_id: int,
        task_type: StudyTaskType,
        question_ids: list[int] | None,
    ) -> list[StudyTaskQuestionCandidate]:
        """把手动题目 ID 转成任务题目候选。"""

        if not question_ids:
            if task_type == StudyTaskType.QUESTION_PRACTICE:
                raise InvalidStudyTaskQuestionError("question_practice task requires question_ids")
            return []

        stmt = (
            select(Question.id)
            .join(QuestionSkill, QuestionSkill.question_id == Question.id)
            .where(
                Question.id.in_(question_ids),
                QuestionSkill.skill_id == skill_id,
                Question.status == QuestionStatus.ACTIVE,
                Question.review_status == QuestionReviewStatus.APPROVED,
            )
        )
        if task_type == StudyTaskType.QUESTION_PRACTICE:
            stmt = stmt.where(Question.question_type.in_(AUTO_GRADABLE_QUESTION_TYPES))

        valid_ids = set((await db.scalars(stmt)).all())
        if valid_ids != set(question_ids):
            raise InvalidStudyTaskQuestionError()

        return [
            StudyTaskQuestionCandidate(question_id=question_id, sort_order=sort_order)
            for sort_order, question_id in enumerate(question_ids, start=1)
        ]

    @staticmethod
    def _add_progress(
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        total_question_count: int,
    ) -> None:
        """初始化任务进度聚合。"""

        db.add(
            StudyTaskProgress(
                user_id=user_id,
                study_task_id=task_id,
                total_question_count=total_question_count,
                completed_question_count=0,
                practiced_count=0,
                correct_count=0,
                incorrect_count=0,
                skipped_count=0,
                progress_percent=Decimal("0.00"),
                score=None,
            )
        )

    @staticmethod
    def _add_task_questions(
        db: AsyncSession,
        *,
        task_id: int,
        question_candidates: list[StudyTaskQuestionCandidate],
    ) -> None:
        """批量添加任务题目清单。"""

        for candidate in question_candidates:
            db.add(
                StudyTaskQuestion(
                    study_task_id=task_id,
                    question_id=candidate.question_id,
                    sort_order=candidate.sort_order,
                )
            )

    async def _grade_attempt(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        payload: StudyTaskQuestionAttemptCommand,
    ) -> _AttemptGradeResult:
        """MVP 自动判定题目作答结果。"""

        if payload.selected_option_ids is None:
            raise InvalidStudyTaskAnswerPayloadError()

        question_type, option_rows = await self._get_question_options_for_grading(
            db,
            question_id=question_id,
        )
        self._validate_selected_options(
            question_type=question_type,
            option_rows=option_rows,
            selected_option_ids=payload.selected_option_ids,
        )
        official_answer = await self._get_official_answer(db, question_id=question_id)

        correct_options = [
            (option_id, explanation)
            for option_id, is_correct, explanation in option_rows
            if is_correct
        ]
        selected_option_ids = set(payload.selected_option_ids)
        correct_option_ids = {option_id for option_id, _explanation in correct_options}
        is_correct = selected_option_ids == correct_option_ids and bool(correct_option_ids)
        return _AttemptGradeResult(
            result=(
                StudyTaskQuestionResult.CORRECT if is_correct else StudyTaskQuestionResult.INCORRECT
            ),
            score=Decimal("100.00") if is_correct else Decimal("0.00"),
            feedback=StudyTaskAttemptFeedback(
                correct_option_ids=sorted(correct_option_ids),
                explanation=self._join_option_explanations(correct_options),
                official_answer=official_answer,
            ),
        )

    async def _get_question_options_for_grading(
        self,
        db: AsyncSession,
        *,
        question_id: int,
    ) -> tuple[QuestionType, list[tuple[int, bool, str | None]]]:
        """读取题型和选项，用于作答校验与自动判分。"""

        stmt = (
            select(
                Question.question_type,
                QuestionOption.id,
                QuestionOption.is_correct,
                QuestionOption.explanation,
            )
            .join(QuestionOption, QuestionOption.question_id == Question.id)
            .where(
                Question.id == question_id,
                Question.question_type.in_(AUTO_GRADABLE_QUESTION_TYPES),
            )
            .order_by(QuestionOption.sort_order.asc(), QuestionOption.id.asc())
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            raise StudyTaskQuestionTypeNotSupportedError()

        question_type = rows[0][0]
        return (
            question_type,
            [
                (option_id, is_correct, explanation)
                for _question_type, option_id, is_correct, explanation in rows
            ],
        )

    @staticmethod
    async def _get_official_answer(db: AsyncSession, *, question_id: int) -> str | None:
        """读取题目的官方答案文本。"""

        stmt = (
            select(QuestionAnswer.content)
            .where(
                QuestionAnswer.question_id == question_id,
                QuestionAnswer.source_type == ContentSourceType.OFFICIAL,
                QuestionAnswer.status == QuestionAnswerStatus.ACTIVE,
            )
            .order_by(QuestionAnswer.created_at.desc(), QuestionAnswer.id.desc())
            .limit(1)
        )
        return await db.scalar(stmt)

    @staticmethod
    def _join_option_explanations(correct_options: list[tuple[int, str | None]]) -> str | None:
        """合并正确选项解释。"""

        explanations = [
            explanation.strip()
            for _option_id, explanation in correct_options
            if explanation and explanation.strip()
        ]
        if not explanations:
            return None
        return "\n".join(explanations)

    @staticmethod
    def _build_generated_source_key(gap: StudyTaskGapCandidate) -> str:
        """生成任务幂等键。"""

        return f"target:{gap.target_id}:skill:{gap.skill_id}:{gap.match_status}"

    @staticmethod
    def _source_from_gap_status(match_status: str) -> StudyTaskSource:
        """把技能缺口状态映射为任务来源。"""

        if match_status == "missing":
            return StudyTaskSource.MATCH_MISSING_SKILL
        return StudyTaskSource.MATCH_WEAK_SKILL

    @staticmethod
    def _build_generated_description(gap: StudyTaskGapCandidate) -> str:
        """生成学习任务说明。"""

        job_label = gap.job_title or "目标岗位"
        company_label = f"（{gap.company_name}）" if gap.company_name else ""
        return f"围绕 {job_label}{company_label} 的 {gap.skill_name} 技能缺口练习面试题。"

    @staticmethod
    def _apply_task_status(task: StudyTask, *, status: StudyTaskStatus) -> None:
        """按任务状态维护生命周期时间。"""

        now = datetime.now(UTC)
        task.status = status
        if status == StudyTaskStatus.TODO:
            task.started_at = None
            task.completed_at = None
            task.archived_at = None
        elif status == StudyTaskStatus.IN_PROGRESS:
            task.started_at = task.started_at or now
            task.completed_at = None
            task.archived_at = None
        elif status == StudyTaskStatus.COMPLETED:
            task.started_at = task.started_at or now
            task.completed_at = task.completed_at or now
            task.archived_at = None
        else:
            task.archived_at = task.archived_at or now

    @staticmethod
    def _validate_task_status_transition(
        current: StudyTaskStatus,
        target: StudyTaskStatus,
    ) -> None:
        """校验学习任务状态的 MVP 单向流转规则。"""

        if current == target:
            return

        allowed_transitions: dict[StudyTaskStatus, set[StudyTaskStatus]] = {
            StudyTaskStatus.TODO: {
                StudyTaskStatus.IN_PROGRESS,
                StudyTaskStatus.COMPLETED,
                StudyTaskStatus.ARCHIVED,
            },
            StudyTaskStatus.IN_PROGRESS: {
                StudyTaskStatus.COMPLETED,
                StudyTaskStatus.ARCHIVED,
            },
            StudyTaskStatus.COMPLETED: {StudyTaskStatus.ARCHIVED},
            StudyTaskStatus.ARCHIVED: set(),
        }
        if target not in allowed_transitions[current]:
            raise InvalidStudyTaskStatusTransitionError()

    @staticmethod
    async def _count_task_questions(db: AsyncSession, *, task_id: int) -> int:
        """统计任务内题目总数。"""

        stmt = select(func.count(StudyTaskQuestion.id)).where(
            StudyTaskQuestion.study_task_id == task_id,
        )
        return await db.scalar(stmt) or 0

    @staticmethod
    async def _count_completed_task_questions(db: AsyncSession, *, task_id: int) -> int:
        """统计任务内已完成或已跳过题目数。"""

        stmt = select(func.count(StudyTaskQuestion.id)).where(
            StudyTaskQuestion.study_task_id == task_id,
            StudyTaskQuestion.status.in_(
                (StudyTaskQuestionStatus.DONE, StudyTaskQuestionStatus.SKIPPED),
            ),
        )
        return await db.scalar(stmt) or 0

    @staticmethod
    async def _get_or_create_progress(
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
    ) -> StudyTaskProgress:
        """读取或初始化任务进度聚合。"""

        stmt = (
            select(StudyTaskProgress)
            .where(
                StudyTaskProgress.user_id == user_id,
                StudyTaskProgress.study_task_id == task_id,
            )
            .with_for_update()
        )
        progress = await db.scalar(stmt)
        if progress is not None:
            return progress

        progress = StudyTaskProgress(
            user_id=user_id,
            study_task_id=task_id,
            total_question_count=0,
            completed_question_count=0,
            practiced_count=0,
            correct_count=0,
            incorrect_count=0,
            skipped_count=0,
            progress_percent=Decimal("0.00"),
            score=None,
        )
        db.add(progress)
        await db.flush()
        return progress

    @staticmethod
    def _calculate_progress_percent(
        *,
        completed_question_count: int,
        total_question_count: int,
    ) -> Decimal:
        """按题目完成数计算百分比。"""

        if total_question_count == 0:
            return Decimal("0.00")
        percent = Decimal(completed_question_count * 100) / Decimal(total_question_count)
        return percent.quantize(Decimal("0.01"))

    @staticmethod
    def _calculate_score(*, correct_count: int, incorrect_count: int) -> Decimal | None:
        """按正确/错误次数计算任务综合得分，跳过不进入分母。"""

        denominator = correct_count + incorrect_count
        if denominator == 0:
            return None
        score = Decimal(correct_count * 100) / Decimal(denominator)
        return score.quantize(Decimal("0.01"))

    @staticmethod
    def _validate_selected_options(
        *,
        question_type: QuestionType,
        option_rows: list[tuple[int, bool, str | None]],
        selected_option_ids: list[int],
    ) -> None:
        """校验提交选项是否属于当前题目并符合题型数量规则。"""

        selected_count = len(selected_option_ids)
        if question_type in (QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE):
            if selected_count != 1:
                raise InvalidStudyTaskAnswerPayloadError()
        elif question_type == QuestionType.MULTIPLE_CHOICE and selected_count < 1:
            raise InvalidStudyTaskAnswerPayloadError()

        option_ids = {option_id for option_id, _is_correct, _explanation in option_rows}
        if not set(selected_option_ids).issubset(option_ids):
            raise InvalidStudyTaskAnswerPayloadError()
