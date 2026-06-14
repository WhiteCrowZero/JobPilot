from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.job_collections.models import JobCollection
from job_pilot.modules.job_targets.enums import JobTargetStatus
from job_pilot.modules.job_targets.exceptions import (
    JobPostForTargetNotFoundError,
    JobTargetNotFoundError,
    JobTargetSourceCollectionInvalidError,
)
from job_pilot.modules.job_targets.models import JobTarget
from job_pilot.modules.job_targets.repository import CURRENT_TARGET_STATUSES, JobTargetRepository
from job_pilot.modules.job_targets.schemas import (
    JobTargetCreate,
    JobTargetListParams,
    JobTargetListResponse,
    JobTargetResponse,
    JobTargetUpdate,
)


class JobTargetService:
    """目标岗位 service，负责用户隔离、来源校验、主目标和状态流转。"""

    def __init__(self, repository: JobTargetRepository) -> None:
        self.repository = repository

    async def create_target(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        payload: JobTargetCreate,
    ) -> JobTargetResponse:
        """新增、恢复或重新激活当前用户目标岗位。"""

        create_values = payload.model_dump(exclude={"job_post_id"})
        update_values = payload.model_dump(exclude={"job_post_id"}, exclude_unset=True)
        update_values["source_collection_id"] = payload.source_collection_id

        try:
            await self._ensure_job_exists(db, job_post_id=payload.job_post_id)
            await self._validate_source_collection(
                db,
                user_id=user_id,
                job_post_id=payload.job_post_id,
                source_collection_id=payload.source_collection_id,
            )
            if payload.is_primary:
                await self.repository.clear_primary_targets(db, user_id=user_id)

            target = await self.repository.upsert_active_target(
                db,
                user_id=user_id,
                job_post_id=payload.job_post_id,
                create_values=create_values,
                update_values=update_values,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return self._to_response(target)

    async def list_targets(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: JobTargetListParams,
    ) -> JobTargetListResponse:
        """分页读取当前用户目标岗位。"""

        targets = await self.repository.list_user_targets(db, user_id=user_id, params=params)
        has_next = len(targets) > params.page_size
        page_items = targets[: params.page_size]
        return JobTargetListResponse(
            items=[self._to_response(target) for target in page_items],
            page=params.page,
            page_size=params.page_size,
            total=None,
            has_next=has_next,
        )

    async def update_target(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        payload: JobTargetUpdate,
    ) -> JobTargetResponse:
        """更新当前用户目标岗位详情和状态。"""

        try:
            target = await self.repository.get_user_target(
                db,
                user_id=user_id,
                target_id=target_id,
            )
            if target is None:
                raise JobTargetNotFoundError()

            values = self._build_update_values(payload)
            if "status" in values:
                self._apply_status_lifecycle(target=target, values=values)
            else:
                self._apply_primary_lifecycle(target=target, values=values)
            if self._will_be_current_primary(target=target, values=values):
                await self.repository.clear_primary_targets(
                    db,
                    user_id=user_id,
                    exclude_target_id=target.id,
                )

            if values:
                target = await self.repository.update_target(db, target=target, values=values)
                await db.commit()
        except Exception:
            await db.rollback()
            raise

        return self._to_response(target)

    async def archive_target(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
    ) -> JobTargetResponse:
        """归档当前用户目标岗位。"""

        return await self.update_target(
            db,
            user_id=user_id,
            target_id=target_id,
            payload=JobTargetUpdate(status=JobTargetStatus.ARCHIVED),
        )

    async def _ensure_job_exists(self, db: AsyncSession, *, job_post_id: int) -> None:
        if not await self.repository.job_post_exists(db, job_post_id=job_post_id):
            raise JobPostForTargetNotFoundError()

    async def _validate_source_collection(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        job_post_id: int,
        source_collection_id: int | None,
    ) -> JobCollection | None:
        if source_collection_id is None:
            return None

        source_collection = await self.repository.get_source_collection(
            db,
            user_id=user_id,
            collection_id=source_collection_id,
        )
        if source_collection is None or source_collection.job_post_id != job_post_id:
            raise JobTargetSourceCollectionInvalidError()
        return source_collection

    @staticmethod
    def _build_update_values(payload: JobTargetUpdate) -> dict[str, object]:
        values: dict[str, object] = {}
        for field_name in payload.model_fields_set:
            values[field_name] = getattr(payload, field_name)
        return values

    @staticmethod
    def _apply_status_lifecycle(target: JobTarget, values: dict[str, object]) -> None:
        next_status = values.get("status", target.status)
        if next_status in CURRENT_TARGET_STATUSES:
            values["completed_at"] = None
            values["archived_at"] = None
            return

        if next_status == JobTargetStatus.COMPLETED:
            values["completed_at"] = func.now()
            values["archived_at"] = None
            values["is_primary"] = False
            return

        if next_status == JobTargetStatus.ARCHIVED:
            values["archived_at"] = func.now()
            values["is_primary"] = False
            return

        if values.get("is_primary") is True:
            values["is_primary"] = False

    @staticmethod
    def _apply_primary_lifecycle(target: JobTarget, values: dict[str, object]) -> None:
        if values.get("is_primary") is True and target.status not in CURRENT_TARGET_STATUSES:
            values["is_primary"] = False

    @staticmethod
    def _will_be_current_primary(target: JobTarget, values: dict[str, object]) -> bool:
        next_status = values.get("status", target.status)
        next_is_primary = values.get("is_primary", target.is_primary)
        return next_is_primary is True and next_status in CURRENT_TARGET_STATUSES

    @staticmethod
    def _to_response(target: JobTarget) -> JobTargetResponse:
        return JobTargetResponse(
            id=target.id,
            user_id=target.user_id,
            job_post_id=target.job_post_id,
            source_collection_id=target.source_collection_id,
            status=target.status,
            priority=target.priority,
            is_primary=target.is_primary,
            note=target.note,
            target_date=target.target_date,
            targeted_at=target.targeted_at,
            completed_at=target.completed_at,
            archived_at=target.archived_at,
            created_at=target.created_at,
            updated_at=target.updated_at,
        )


def build_job_target_service() -> JobTargetService:
    """组装目标岗位 service 的默认依赖。"""

    return JobTargetService(repository=JobTargetRepository())
