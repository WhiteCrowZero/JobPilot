from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.job_posts.models import JobPost
from job_pilot.modules.job_skills.models import JobPostSkill, Skill
from job_pilot.modules.job_targets.enums import JobTargetStatus
from job_pilot.modules.job_targets.policies import CURRENT_TARGET_STATUSES
from job_pilot.modules.user_skills.enums import UserSkillStatus
from job_pilot.modules.user_skills.models import UserSkill


@dataclass(frozen=True)
class JobSkillSnapshot:
    """岗位技能只读快照。"""

    skill_id: int
    skill_name: str


@dataclass(frozen=True)
class UserSkillSnapshot:
    """用户 active 技能只读快照。"""

    skill_id: int
    skill_name: str
    proficiency_level: int


@dataclass(frozen=True)
class JobTargetSnapshot:
    """目标岗位只读快照。"""

    target_id: int
    job_post_id: int
    status: JobTargetStatus
    priority: int
    is_primary: bool


@dataclass(frozen=True)
class TargetSkillSummaryRow:
    """目标岗位技能摘要聚合行。"""

    skill_id: int
    skill_name: str
    target_count: int


class JobMatchRepository:
    """技能覆盖分析相关只读数据库操作。"""

    async def job_post_exists(self, db: AsyncSession, *, job_post_id: int) -> bool:
        """判断岗位是否存在且未被软删除。"""

        stmt = (
            select(JobPost.id)
            .where(
                JobPost.id == job_post_id,
                JobPost.deleted_at.is_(None),
            )
            .limit(1)
        )
        return await db.scalar(stmt) is not None

    async def list_job_skills(
        self,
        db: AsyncSession,
        *,
        job_post_id: int,
    ) -> list[JobSkillSnapshot]:
        """读取某个岗位的标准技能标签。"""

        stmt = (
            select(Skill.id, Skill.name)
            .join(JobPostSkill, JobPostSkill.skill_id == Skill.id)
            .where(JobPostSkill.job_post_id == job_post_id)
            .order_by(Skill.name.asc())
        )
        result = await db.execute(stmt)
        return [
            JobSkillSnapshot(skill_id=skill_id, skill_name=skill_name)
            for skill_id, skill_name in result.all()
        ]

    async def list_user_active_skills(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skill_ids: list[int] | None = None,
    ) -> list[UserSkillSnapshot]:
        """读取当前用户 active 技能画像，可按技能 ID 限定范围。"""

        if skill_ids == []:
            return []

        stmt = (
            select(UserSkill.skill_id, Skill.name, UserSkill.proficiency_level)
            .join(Skill, Skill.id == UserSkill.skill_id)
            .where(
                UserSkill.user_id == user_id,
                UserSkill.status == UserSkillStatus.ACTIVE,
            )
            .order_by(Skill.name.asc())
        )
        if skill_ids is not None:
            stmt = stmt.where(UserSkill.skill_id.in_(skill_ids))

        result = await db.execute(stmt)
        return [
            UserSkillSnapshot(
                skill_id=skill_id,
                skill_name=skill_name,
                proficiency_level=proficiency_level,
            )
            for skill_id, skill_name, proficiency_level in result.all()
        ]

    async def get_user_target(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
    ) -> JobTargetSnapshot | None:
        """按用户读取目标岗位，避免跨用户访问。"""

        from job_pilot.modules.job_targets.models import JobTarget

        stmt = select(
            JobTarget.id,
            JobTarget.job_post_id,
            JobTarget.status,
            JobTarget.priority,
            JobTarget.is_primary,
        ).where(
            JobTarget.user_id == user_id,
            JobTarget.id == target_id,
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            return None
        target_id_value, job_post_id, status, priority, is_primary = row
        return JobTargetSnapshot(
            target_id=target_id_value,
            job_post_id=job_post_id,
            status=status,
            priority=priority,
            is_primary=is_primary,
        )

    async def get_current_target_for_job(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        job_post_id: int,
    ) -> JobTargetSnapshot | None:
        """读取当前用户对某岗位的 active/paused 目标记录。"""

        from job_pilot.modules.job_targets.models import JobTarget

        stmt = (
            select(
                JobTarget.id,
                JobTarget.job_post_id,
                JobTarget.status,
                JobTarget.priority,
                JobTarget.is_primary,
            )
            .where(
                JobTarget.user_id == user_id,
                JobTarget.job_post_id == job_post_id,
                JobTarget.status.in_(CURRENT_TARGET_STATUSES),
            )
            .order_by(JobTarget.is_primary.desc(), JobTarget.priority.asc(), JobTarget.id.desc())
            .limit(1)
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            return None
        target_id, job_post_id_value, status, priority, is_primary = row
        return JobTargetSnapshot(
            target_id=target_id,
            job_post_id=job_post_id_value,
            status=status,
            priority=priority,
            is_primary=is_primary,
        )

    async def list_current_targets(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> list[JobTargetSnapshot]:
        """读取当前用户 active/paused 目标岗位，用于目标集合分析。"""

        from job_pilot.modules.job_targets.models import JobTarget

        stmt = (
            select(
                JobTarget.id,
                JobTarget.job_post_id,
                JobTarget.status,
                JobTarget.priority,
                JobTarget.is_primary,
            )
            .where(
                JobTarget.user_id == user_id,
                JobTarget.status.in_(CURRENT_TARGET_STATUSES),
            )
            .order_by(
                JobTarget.is_primary.desc(),
                JobTarget.priority.asc(),
                JobTarget.targeted_at.desc(),
                JobTarget.id.desc(),
            )
        )
        result = await db.execute(stmt)
        return [
            JobTargetSnapshot(
                target_id=target_id,
                job_post_id=job_post_id,
                status=status,
                priority=priority,
                is_primary=is_primary,
            )
            for target_id, job_post_id, status, priority, is_primary in result.all()
        ]

    async def list_skill_summary_for_jobs(
        self,
        db: AsyncSession,
        *,
        job_post_ids: list[int],
        limit: int,
    ) -> list[TargetSkillSummaryRow]:
        """统计一组目标岗位中每个技能出现过多少次。"""

        if not job_post_ids:
            return []

        stmt = (
            select(
                Skill.id,
                Skill.name,
                func.count(JobPostSkill.job_post_id).label("target_count"),
            )
            .join(JobPostSkill, JobPostSkill.skill_id == Skill.id)
            .where(JobPostSkill.job_post_id.in_(job_post_ids))
            .group_by(Skill.id, Skill.name)
            .order_by(func.count(JobPostSkill.job_post_id).desc(), Skill.name.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [
            TargetSkillSummaryRow(
                skill_id=skill_id,
                skill_name=skill_name,
                target_count=target_count,
            )
            for skill_id, skill_name, target_count in result.all()
        ]
