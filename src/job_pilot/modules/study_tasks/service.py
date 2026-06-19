from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.pagination import trim_page_items
from job_pilot.modules.study_tasks.contracts import (
    StudyTaskAttemptMutationResult,
    StudyTaskCreateCommand,
    StudyTaskGapCandidate,
    StudyTaskGenerateFromTargetCommand,
    StudyTaskListQuery,
    StudyTaskProgressSnapshot,
    StudyTaskQuestionAttemptCommand,
    StudyTaskQuestionSkipCommand,
    StudyTaskUpdateCommand,
)
from job_pilot.modules.study_tasks.exceptions import (
    NoStudyTaskSkillGapAvailableError,
    StudyTaskNotFoundError,
    StudyTaskQuestionNotFoundError,
    StudyTaskTargetNotFoundError,
)
from job_pilot.modules.study_tasks.models import (
    StudyTask,
    StudyTaskProgress,
    StudyTaskQuestion,
    StudyTaskSnapshot,
)
from job_pilot.modules.study_tasks.repository import StudyTaskRepository
from job_pilot.modules.study_tasks.schemas import (
    StudyTaskAttemptFeedbackResponse,
    StudyTaskAttemptResponse,
    StudyTaskDetailResponse,
    StudyTaskGenerationResponse,
    StudyTaskGenerationSkippedItem,
    StudyTaskListItem,
    StudyTaskListResponse,
    StudyTaskProgressResponse,
    StudyTaskQuestionAttemptStateResponse,
    StudyTaskQuestionContentResponse,
    StudyTaskQuestionItem,
    StudyTaskQuestionOptionResponse,
    StudyTaskSnapshotResponse,
    StudyTaskUpdateResponse,
)
from job_pilot.modules.user_skills.enums import UserSkillProficiencyLevel


class StudyTaskService:
    """学习任务 service，负责用户隔离下的任务生成、作答和进度更新流程。"""

    def __init__(self, repository: StudyTaskRepository) -> None:
        self.repository = repository

    async def generate_from_target(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        payload: StudyTaskGenerateFromTargetCommand,
    ) -> StudyTaskGenerationResponse:
        """根据目标岗位技能缺口生成学习任务。"""

        target = await self.repository.get_current_target_for_generation(
            db,
            user_id=user_id,
            target_id=target_id,
        )
        if target is None:
            raise StudyTaskTargetNotFoundError()

        gaps = await self.repository.list_target_skill_gaps(
            db,
            user_id=user_id,
            target_id=target_id,
            required_level=payload.required_level,
        )
        selected_gaps = self._select_generation_gaps(gaps, payload=payload)
        if not selected_gaps:
            raise NoStudyTaskSkillGapAvailableError()

        items: list[StudyTaskListItem] = []
        created_count = 0
        reused_count = 0
        skipped_skill_count = 0
        skipped_items: list[StudyTaskGenerationSkippedItem] = []

        for gap in selected_gaps:
            if created_count + reused_count >= payload.max_tasks:
                break
            question_candidates = await self.repository.list_question_candidates_for_skill(
                db,
                skill_id=gap.skill_id,
                limit=payload.question_count_per_task,
                difficulty=payload.difficulty,
            )
            if not question_candidates:
                skipped_skill_count += 1
                skipped_items.append(
                    StudyTaskGenerationSkippedItem(
                        skill_id=gap.skill_id,
                        skill_name=gap.skill_name,
                        reason="no_question",
                    )
                )
                continue

            task, created = await self.repository.create_or_reuse_generated_task(
                db,
                user_id=user_id,
                gap=gap,
                question_candidates=question_candidates,
                command=payload,
            )
            items.append(self._to_list_item(task))
            if created:
                created_count += 1
            else:
                reused_count += 1

        return StudyTaskGenerationResponse(
            items=items,
            created_count=created_count,
            reused_count=reused_count,
            skipped_skill_count=skipped_skill_count,
            skipped_items=skipped_items,
        )

    async def list_tasks(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: StudyTaskListQuery,
    ) -> StudyTaskListResponse:
        """分页查询当前用户学习任务。"""

        tasks = await self.repository.list_user_tasks(db, user_id=user_id, params=params)
        page_items, has_next = trim_page_items(tasks, page_size=params.page_size)
        return StudyTaskListResponse(
            items=[self._to_list_item(task) for task in page_items],
            page=params.page,
            page_size=params.page_size,
            total=None,
            has_next=has_next,
        )

    async def create_task(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        payload: StudyTaskCreateCommand,
    ) -> StudyTaskListItem:
        """手动创建当前用户学习任务。"""

        task = await self.repository.create_user_task(db, user_id=user_id, payload=payload)
        return self._to_list_item(task)

    async def get_task_detail(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
    ) -> StudyTaskDetailResponse:
        """读取当前用户学习任务详情。"""

        task = await self.repository.get_user_task_detail(db, user_id=user_id, task_id=task_id)
        if task is None:
            raise StudyTaskNotFoundError()
        list_item = self._to_list_item(task)
        return StudyTaskDetailResponse(
            **list_item.model_dump(),
            snapshot=self._to_snapshot_response(task.snapshot),
            questions=[
                self._to_question_item(task_question)
                for task_question in sorted(
                    task.questions,
                    key=lambda item: (item.sort_order, item.id),
                )
            ],
        )

    async def update_task(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        payload: StudyTaskUpdateCommand,
    ) -> StudyTaskUpdateResponse:
        """更新当前用户学习任务本体。"""

        task = await self.repository.update_task_metadata(
            db, user_id=user_id, task_id=task_id, payload=payload
        )
        if task is None:
            raise StudyTaskNotFoundError()
        return self._to_update_response(task)

    async def archive_task(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
    ) -> StudyTaskUpdateResponse:
        """归档当前用户学习任务。"""

        task = await self.repository.archive_user_task(db, user_id=user_id, task_id=task_id)
        if task is None:
            raise StudyTaskNotFoundError()
        return self._to_update_response(task)

    async def submit_attempt(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        task_question_id: int,
        payload: StudyTaskQuestionAttemptCommand,
    ) -> StudyTaskAttemptResponse:
        """提交任务题目作答。"""

        result = await self.repository.submit_question_attempt(
            db,
            user_id=user_id,
            task_id=task_id,
            task_question_id=task_question_id,
            payload=payload,
        )
        if result is None:
            raise StudyTaskQuestionNotFoundError()
        return self._to_attempt_response(result)

    async def skip_task_question(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        task_question_id: int,
        payload: StudyTaskQuestionSkipCommand,
    ) -> StudyTaskAttemptResponse:
        """跳过任务内题目。"""

        result = await self.repository.skip_task_question(
            db,
            user_id=user_id,
            task_id=task_id,
            task_question_id=task_question_id,
            payload=payload,
        )
        if result is None:
            raise StudyTaskQuestionNotFoundError()
        return self._to_attempt_response(result)

    @staticmethod
    def _select_generation_gaps(
        gaps: list[StudyTaskGapCandidate],
        *,
        payload: StudyTaskGenerateFromTargetCommand,
    ) -> list[StudyTaskGapCandidate]:
        """按请求开关筛选 missing/weak 技能缺口。"""

        selected_gaps: list[StudyTaskGapCandidate] = []
        for gap in gaps:
            if gap.match_status == "missing" and payload.include_missing_skills:
                selected_gaps.append(gap)
            if gap.match_status == "weak" and payload.include_weak_skills:
                selected_gaps.append(gap)
        return selected_gaps

    def _to_list_item(self, task: StudyTask) -> StudyTaskListItem:
        """转换学习任务列表项。"""

        return StudyTaskListItem(
            id=task.id,
            user_id=task.user_id,
            skill_id=task.skill_id,
            skill_name=task.skill.name,
            source=task.source,
            source_key=task.source_key,
            task_type=task.task_type,
            status=task.status,
            title=task.title,
            description=task.description,
            priority=task.priority,
            estimated_minutes=task.estimated_minutes,
            actual_minutes=task.actual_minutes,
            planned_start_date=task.planned_start_date,
            due_date=task.due_date,
            started_at=task.started_at,
            completed_at=task.completed_at,
            archived_at=task.archived_at,
            progress=self._to_progress_response(task.progress),
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @staticmethod
    def _to_progress_response(progress: StudyTaskProgress | None) -> StudyTaskProgressResponse:
        """转换学习任务进度，未初始化时返回 0 进度。"""

        if progress is None:
            return StudyTaskProgressResponse(
                total_question_count=0,
                completed_question_count=0,
                practiced_count=0,
                correct_count=0,
                incorrect_count=0,
                skipped_count=0,
                progress_percent=Decimal("0.00"),
                score=None,
                last_practiced_at=None,
                completed_at=None,
            )
        return StudyTaskProgressResponse(
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
        )

    @staticmethod
    def _to_progress_snapshot_response(
        progress: StudyTaskProgressSnapshot,
    ) -> StudyTaskProgressResponse:
        """转换作答动作返回的进度快照。"""

        return StudyTaskProgressResponse(
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
        )

    @staticmethod
    def _to_snapshot_response(
        snapshot: StudyTaskSnapshot | None,
    ) -> StudyTaskSnapshotResponse | None:
        """转换任务生成快照。"""

        if snapshot is None:
            return None
        return StudyTaskSnapshotResponse(
            target_id=snapshot.target_id,
            job_post_id=snapshot.job_post_id,
            skill_name_snapshot=snapshot.skill_name_snapshot,
            job_title_snapshot=snapshot.job_title_snapshot,
            company_name_snapshot=snapshot.company_name_snapshot,
            target_title_snapshot=snapshot.target_title_snapshot,
            match_status_snapshot=snapshot.match_status_snapshot,
            required_level_snapshot=(
                UserSkillProficiencyLevel(snapshot.required_level_snapshot)
                if snapshot.required_level_snapshot is not None
                else None
            ),
            user_level_snapshot=(
                UserSkillProficiencyLevel(snapshot.user_level_snapshot)
                if snapshot.user_level_snapshot is not None
                else None
            ),
            is_primary_target_snapshot=snapshot.is_primary_target_snapshot,
            target_priority_snapshot=snapshot.target_priority_snapshot,
        )

    def _to_question_item(self, task_question: StudyTaskQuestion) -> StudyTaskQuestionItem:
        """转换任务详情中的题目项。"""

        question = task_question.question
        return StudyTaskQuestionItem(
            task_question_id=task_question.id,
            question_id=task_question.question_id,
            status=task_question.status,
            last_result=task_question.last_result,
            last_score=task_question.last_score,
            attempt_count=task_question.attempt_count,
            sort_order=task_question.sort_order,
            assigned_at=task_question.assigned_at,
            completed_at=task_question.completed_at,
            skipped_at=task_question.skipped_at,
            question=StudyTaskQuestionContentResponse(
                id=question.id,
                title=question.title,
                question_text=question.question_text,
                question_type=question.question_type,
                difficulty=question.difficulty,
                options=[
                    StudyTaskQuestionOptionResponse(
                        id=option.id,
                        option_label=option.option_label,
                        content=option.content,
                        sort_order=option.sort_order,
                    )
                    for option in sorted(question.options, key=lambda item: item.sort_order)
                ],
            ),
        )

    def _to_update_response(self, task: StudyTask) -> StudyTaskUpdateResponse:
        """转换任务本体更新响应。"""

        return StudyTaskUpdateResponse(
            task_id=task.id,
            user_id=task.user_id,
            status=task.status,
            title=task.title,
            description=task.description,
            priority=task.priority,
            estimated_minutes=task.estimated_minutes,
            actual_minutes=task.actual_minutes,
            planned_start_date=task.planned_start_date,
            due_date=task.due_date,
            started_at=task.started_at,
            completed_at=task.completed_at,
            archived_at=task.archived_at,
            progress=self._to_progress_response(task.progress),
        )

    def _to_attempt_response(
        self,
        result: StudyTaskAttemptMutationResult,
    ) -> StudyTaskAttemptResponse:
        """转换提交作答响应。"""

        task_question_state = StudyTaskQuestionAttemptStateResponse(
            id=result.task_question_id,
            task_id=result.task_id,
            question_id=result.question_id,
            status=result.task_question_status,
            last_result=result.task_question_last_result,
            last_score=result.task_question_last_score,
            attempt_count=result.task_question_attempt_count,
            completed_at=result.task_question_completed_at,
            skipped_at=result.task_question_skipped_at,
        )
        return StudyTaskAttemptResponse(
            id=result.attempt_id,
            task_id=result.task_id,
            task_question_id=result.task_question_id,
            question_id=result.question_id,
            result=result.result,
            score=result.score,
            selected_option_ids=result.selected_option_ids,
            answer_text=result.answer_text,
            duration_seconds=result.duration_seconds,
            attempted_at=result.attempted_at,
            feedback=StudyTaskAttemptFeedbackResponse(
                correct_option_ids=result.feedback.correct_option_ids,
                explanation=result.feedback.explanation,
                official_answer=result.feedback.official_answer,
            ),
            task_question=task_question_state,
            progress=self._to_progress_snapshot_response(result.progress),
        )


def build_study_task_service() -> StudyTaskService:
    """组装学习任务 service 的默认依赖。"""

    return StudyTaskService(repository=StudyTaskRepository())
