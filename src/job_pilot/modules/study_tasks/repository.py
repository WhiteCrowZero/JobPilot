from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.questions.enums import QuestionDifficulty
from job_pilot.modules.study_tasks.contracts import (
    StudyTaskAttemptMutationResult,
    StudyTaskCreateCommand,
    StudyTaskGapCandidate,
    StudyTaskGenerateFromTargetCommand,
    StudyTaskListQuery,
    StudyTaskQuestionAttemptCommand,
    StudyTaskQuestionCandidate,
    StudyTaskQuestionSkipCommand,
    StudyTaskUpdateCommand,
)
from job_pilot.modules.study_tasks.models import StudyTask


class StudyTaskRepository:
    """学习任务数据库操作。

    本阶段先固定 repository 方法边界，具体 SQL 查询和写入逻辑后续补齐。
    """

    async def list_target_skill_gaps(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        required_level: int,
    ) -> list[StudyTaskGapCandidate]:
        """查询目标岗位的 missing/weak 技能缺口候选项。"""

        _ = (db, user_id, target_id, required_level)
        return []

    async def list_question_candidates_for_skill(
        self,
        db: AsyncSession,
        *,
        skill_id: int,
        limit: int,
        difficulty: QuestionDifficulty | None,
    ) -> list[StudyTaskQuestionCandidate]:
        """查询某个技能可加入任务的题目候选项。"""

        _ = (db, skill_id, limit, difficulty)
        return []

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

        _ = (db, user_id, gap, question_candidates, command)
        raise NotImplementedError("Study task generation persistence is not implemented yet")

    async def create_user_task(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        payload: StudyTaskCreateCommand,
    ) -> StudyTask | None:
        """手动创建当前用户学习任务。"""

        _ = (db, user_id, payload)
        return None

    async def list_user_tasks(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: StudyTaskListQuery,
    ) -> list[StudyTask]:
        """分页查询当前用户学习任务。"""

        _ = (db, user_id, params)
        return []

    async def get_user_task_detail(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
    ) -> StudyTask | None:
        """读取当前用户学习任务详情。"""

        _ = (db, user_id, task_id)
        return None

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

        _ = (db, user_id, task_id, task_question_id, payload)
        return None

    async def update_task_metadata(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        payload: StudyTaskUpdateCommand,
    ) -> StudyTask | None:
        """更新当前用户学习任务本体元数据。"""

        _ = (db, user_id, task_id, payload)
        return None

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

        _ = (db, user_id, task_id, task_question_id, payload)
        return None
