from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from job_pilot.core.search import fetch_offset_page
from job_pilot.db.upsert import upsert_restoring_record
from job_pilot.modules.job_collections.enums import JobCollectionStatus
from job_pilot.modules.job_collections.models import JobCollection
from job_pilot.modules.job_posts.models import JobPost
from job_pilot.modules.job_targets.contracts import JobTargetListQuery
from job_pilot.modules.job_targets.enums import JobTargetStatus
from job_pilot.modules.job_targets.models import JobTarget
from job_pilot.modules.job_targets.policies import CURRENT_TARGET_STATUSES


class JobTargetRepository:
    """目标岗位数据库操作。"""

    async def job_post_exists(self, db: AsyncSession, *, job_post_id: int) -> bool:
        """判断岗位是否存在且未删除。"""

        stmt = (
            select(JobPost.id)
            .where(
                JobPost.id == job_post_id,
                JobPost.deleted_at.is_(None),
            )
            .limit(1)
        )
        return await db.scalar(stmt) is not None

    async def get_source_collection(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        collection_id: int,
    ) -> JobCollection | None:
        """读取当前用户 active 来源收藏。"""

        stmt = select(JobCollection).where(
            JobCollection.user_id == user_id,
            JobCollection.id == collection_id,
            JobCollection.status == JobCollectionStatus.ACTIVE,
        )
        return await db.scalar(stmt)

    async def get_user_target(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
    ) -> JobTarget | None:
        """按用户读取目标岗位，避免跨用户访问。"""

        stmt = select(JobTarget).where(
            JobTarget.user_id == user_id,
            JobTarget.id == target_id,
        )
        return await db.scalar(stmt)

    async def list_user_targets(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: JobTargetListQuery,
    ) -> list[JobTarget]:
        """分页读取当前用户目标岗位。"""

        conditions: list[ColumnElement[bool]] = [JobTarget.user_id == user_id]
        if params.statuses:
            conditions.append(JobTarget.status.in_(params.statuses))
        else:
            conditions.append(JobTarget.status.in_(CURRENT_TARGET_STATUSES))

        stmt = (
            select(JobTarget)
            .where(*conditions)
            .order_by(
                JobTarget.is_primary.desc(),
                JobTarget.priority.asc(),
                JobTarget.targeted_at.desc(),
                JobTarget.id.desc(),
            )
        )
        return await fetch_offset_page(
            db,
            stmt,
            offset=params.offset,
            limit=params.limit,
        )

    async def clear_primary_targets(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        exclude_target_id: int | None = None,
    ) -> None:
        """清除当前用户其他当前主目标。"""

        conditions: list[ColumnElement[bool]] = [
            JobTarget.user_id == user_id,
            JobTarget.is_primary.is_(True),
            JobTarget.status.in_(CURRENT_TARGET_STATUSES),
        ]
        if exclude_target_id is not None:
            conditions.append(JobTarget.id != exclude_target_id)

        stmt = (
            update(JobTarget)
            .where(*conditions)
            .values(
                is_primary=False,
                updated_at=func.now(),
            )
        )
        await db.execute(stmt)

    async def upsert_active_target(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        job_post_id: int,
        create_values: dict[str, object],
        update_values: dict[str, object],
    ) -> JobTarget:
        """新增或恢复 active 目标岗位。"""

        return await upsert_restoring_record(
            db,
            model=JobTarget,
            conflict_constraint="uq_job_targets_user_job",
            identity_values={
                "user_id": user_id,
                "job_post_id": job_post_id,
            },
            create_values=create_values,
            restore_values={
                "status": JobTargetStatus.ACTIVE,
                "targeted_at": func.now(),
                "completed_at": None,
                "archived_at": None,
            },
            update_values=update_values,
        )

    async def update_target(
        self,
        db: AsyncSession,
        *,
        target: JobTarget,
        values: dict[str, object],
    ) -> JobTarget:
        """更新目标岗位可编辑字段和生命周期字段。"""

        values["updated_at"] = func.now()
        stmt = (
            update(JobTarget)
            .where(JobTarget.id == target.id)
            .values(**values)
            .returning(JobTarget)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one()
