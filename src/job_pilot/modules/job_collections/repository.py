from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from job_pilot.core.search import fetch_offset_page
from job_pilot.db.upsert import upsert_restoring_record
from job_pilot.modules.job_collections.contracts import JobCollectionListQuery
from job_pilot.modules.job_collections.enums import (
    JobCollectionFolderStatus,
    JobCollectionStatus,
)
from job_pilot.modules.job_collections.models import JobCollection, JobCollectionFolder
from job_pilot.modules.job_posts.models import JobPost

DEFAULT_COLLECTION_FOLDER_NAME = "默认收藏夹"


class JobCollectionFolderRepository:
    """岗位收藏夹数据库操作。"""

    async def create_folder(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        name: str,
        sort_order: int,
    ) -> JobCollectionFolder:
        """创建当前用户收藏夹。"""

        folder = JobCollectionFolder(
            user_id=user_id,
            name=name,
            sort_order=sort_order,
            status=JobCollectionFolderStatus.ACTIVE,
            is_default=False,
        )
        db.add(folder)
        await db.flush()
        await db.refresh(folder)
        return folder

    async def get_or_create_default_folder(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> JobCollectionFolder:
        """读取或创建当前用户默认收藏夹。"""

        existing_stmt = select(JobCollectionFolder).where(
            JobCollectionFolder.user_id == user_id,
            JobCollectionFolder.is_default.is_(True),
        )
        existing_folder = await db.scalar(existing_stmt)
        if existing_folder is not None:
            return existing_folder

        insert_stmt = pg_insert(JobCollectionFolder).values(
            user_id=user_id,
            name=DEFAULT_COLLECTION_FOLDER_NAME,
            sort_order=0,
            status=JobCollectionFolderStatus.ACTIVE,
            is_default=True,
            archived_at=None,
        )
        result = await db.execute(
            insert_stmt.on_conflict_do_update(
                constraint="uq_job_collection_folders_user_name",
                set_={
                    "status": JobCollectionFolderStatus.ACTIVE,
                    "is_default": True,
                    "sort_order": 0,
                    "archived_at": None,
                    "updated_at": func.now(),
                },
            )
            .returning(JobCollectionFolder)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    async def get_user_folder(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        folder_id: int,
        active_only: bool = True,
    ) -> JobCollectionFolder | None:
        """读取当前用户收藏夹，避免跨用户访问。"""

        conditions: list[ColumnElement[bool]] = [
            JobCollectionFolder.user_id == user_id,
            JobCollectionFolder.id == folder_id,
        ]
        if active_only:
            conditions.append(JobCollectionFolder.status == JobCollectionFolderStatus.ACTIVE)
        stmt = select(JobCollectionFolder).where(*conditions)
        return await db.scalar(stmt)

    async def list_active_folders(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> list[JobCollectionFolder]:
        """读取当前用户 active 收藏夹。"""

        stmt = (
            select(JobCollectionFolder)
            .where(
                JobCollectionFolder.user_id == user_id,
                JobCollectionFolder.status == JobCollectionFolderStatus.ACTIVE,
            )
            .order_by(JobCollectionFolder.sort_order.asc(), JobCollectionFolder.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_folder(
        self,
        db: AsyncSession,
        *,
        folder: JobCollectionFolder,
        values: dict[str, object],
    ) -> JobCollectionFolder:
        """更新收藏夹可编辑字段。"""

        values["updated_at"] = func.now()
        stmt = (
            update(JobCollectionFolder)
            .where(JobCollectionFolder.id == folder.id)
            .values(**values)
            .returning(JobCollectionFolder)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def clear_default_folders(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        exclude_folder_id: int | None = None,
    ) -> None:
        """清除当前用户其他默认收藏夹。"""

        conditions: list[ColumnElement[bool]] = [
            JobCollectionFolder.user_id == user_id,
            JobCollectionFolder.is_default.is_(True),
        ]
        if exclude_folder_id is not None:
            conditions.append(JobCollectionFolder.id != exclude_folder_id)

        stmt = (
            update(JobCollectionFolder)
            .where(*conditions)
            .values(is_default=False, updated_at=func.now())
        )
        await db.execute(stmt)

    async def archive_folder(
        self,
        db: AsyncSession,
        *,
        folder: JobCollectionFolder,
    ) -> JobCollectionFolder:
        """归档收藏夹。"""

        stmt = (
            update(JobCollectionFolder)
            .where(JobCollectionFolder.id == folder.id)
            .values(
                status=JobCollectionFolderStatus.ARCHIVED,
                archived_at=func.now(),
                updated_at=func.now(),
            )
            .returning(JobCollectionFolder)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def move_collections_to_default_folder(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        folder_id: int,
        default_folder_id: int,
    ) -> None:
        """把某个收藏夹下的收藏移动到默认收藏夹。"""

        stmt = (
            update(JobCollection)
            .where(
                JobCollection.user_id == user_id,
                JobCollection.folder_id == folder_id,
            )
            .values(folder_id=default_folder_id, updated_at=func.now())
        )
        await db.execute(stmt)


class JobCollectionRepository:
    """岗位收藏数据库操作。"""

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

    async def get_user_collection(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        collection_id: int,
        active_only: bool = True,
    ) -> JobCollection | None:
        """按用户读取收藏，避免跨用户访问。"""

        conditions: list[ColumnElement[bool]] = [
            JobCollection.user_id == user_id,
            JobCollection.id == collection_id,
        ]
        if active_only:
            conditions.append(JobCollection.status == JobCollectionStatus.ACTIVE)
        stmt = select(JobCollection).where(*conditions)
        return await db.scalar(stmt)

    async def list_user_collections(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: JobCollectionListQuery,
    ) -> list[JobCollection]:
        """分页读取当前用户岗位收藏。"""

        conditions: list[ColumnElement[bool]] = [
            JobCollection.user_id == user_id,
            JobCollection.status == JobCollectionStatus.ACTIVE,
        ]
        if params.folder_id is not None:
            conditions.append(JobCollection.folder_id == params.folder_id)

        stmt = (
            select(JobCollection)
            .where(*conditions)
            .order_by(JobCollection.collected_at.desc(), JobCollection.id.desc())
        )
        return await fetch_offset_page(
            db,
            stmt,
            offset=params.offset,
            limit=params.limit,
        )

    async def upsert_active_collection(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        job_post_id: int,
        create_values: dict[str, object],
        update_values: dict[str, object],
    ) -> JobCollection:
        """新增或恢复 active 岗位收藏。"""

        return await upsert_restoring_record(
            db,
            model=JobCollection,
            conflict_constraint="uq_job_collections_user_job",
            identity_values={
                "user_id": user_id,
                "job_post_id": job_post_id,
            },
            create_values=create_values,
            restore_values={
                "status": JobCollectionStatus.ACTIVE,
                "removed_at": None,
                "collected_at": func.now(),
            },
            update_values=update_values,
        )

    async def update_collection(
        self,
        db: AsyncSession,
        *,
        collection: JobCollection,
        values: dict[str, object],
    ) -> JobCollection:
        """更新岗位收藏可编辑字段。"""

        values["updated_at"] = func.now()
        stmt = (
            update(JobCollection)
            .where(JobCollection.id == collection.id)
            .values(**values)
            .returning(JobCollection)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def remove_collection(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        collection_id: int,
    ) -> JobCollection | None:
        """软取消当前用户岗位收藏。"""

        stmt = (
            update(JobCollection)
            .where(
                JobCollection.user_id == user_id,
                JobCollection.id == collection_id,
                JobCollection.status == JobCollectionStatus.ACTIVE,
            )
            .values(
                status=JobCollectionStatus.REMOVED,
                removed_at=func.now(),
                updated_at=func.now(),
            )
            .returning(JobCollection)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
