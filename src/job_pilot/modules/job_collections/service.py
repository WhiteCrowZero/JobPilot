from __future__ import annotations

import logging
from dataclasses import MISSING

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.logging import log_app_event
from job_pilot.core.pagination import trim_page_items
from job_pilot.modules.job_collections.contracts import (
    JobCollectionCreateCommand,
    JobCollectionFolderCreateCommand,
    JobCollectionFolderUpdateCommand,
    JobCollectionListQuery,
    JobCollectionUpdateCommand,
)
from job_pilot.modules.job_collections.exceptions import (
    DefaultJobCollectionFolderCannotArchiveError,
    DefaultJobCollectionFolderConflictError,
    JobCollectionFolderNameConflictError,
    JobCollectionFolderNotFoundError,
    JobCollectionNotFoundError,
    JobPostForCollectionNotFoundError,
)
from job_pilot.modules.job_collections.models import JobCollection, JobCollectionFolder
from job_pilot.modules.job_collections.repository import (
    JobCollectionFolderRepository,
    JobCollectionRepository,
)
from job_pilot.modules.job_collections.schemas import (
    JobCollectionFolderResponse,
    JobCollectionListResponse,
    JobCollectionResponse,
)

logger = logging.getLogger(__name__)


class JobCollectionService:
    """岗位收藏 service，负责用户隔离、归属校验和响应转换。"""

    def __init__(
        self,
        folder_repository: JobCollectionFolderRepository,
        collection_repository: JobCollectionRepository,
    ) -> None:
        self.folder_repository = folder_repository
        self.collection_repository = collection_repository

    async def create_folder(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        payload: JobCollectionFolderCreateCommand,
    ) -> JobCollectionFolderResponse:
        """创建当前用户岗位收藏夹。"""

        await self.folder_repository.get_or_create_default_folder(db, user_id=user_id)
        try:
            folder = await self.folder_repository.create_folder(
                db,
                user_id=user_id,
                name=payload.name,
                sort_order=payload.sort_order,
            )
        except IntegrityError as exc:
            raise JobCollectionFolderNameConflictError() from exc
        log_app_event(
            logger,
            "Job collection folder created",
            extra={
                "event": "job_collections.folder_created",
                "user_id": user_id,
                "folder_id": folder.id,
                "is_default": folder.is_default,
            },
        )
        return self._folder_to_response(folder)

    async def list_folders(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> list[JobCollectionFolderResponse]:
        """查询当前用户 active 收藏夹。"""

        await self.folder_repository.get_or_create_default_folder(db, user_id=user_id)
        folders = await self.folder_repository.list_active_folders(db, user_id=user_id)
        return [self._folder_to_response(folder) for folder in folders]

    async def update_folder(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        folder_id: int,
        payload: JobCollectionFolderUpdateCommand,
    ) -> JobCollectionFolderResponse:
        """更新当前用户岗位收藏夹。"""

        folder = await self.folder_repository.get_user_folder(
            db,
            user_id=user_id,
            folder_id=folder_id,
        )
        if folder is None:
            raise JobCollectionFolderNotFoundError()
        values = self._build_update_values(payload)
        if values:
            try:
                folder = await self.folder_repository.update_folder(
                    db,
                    folder=folder,
                    values=values,
                )
            except IntegrityError as exc:
                raise JobCollectionFolderNameConflictError() from exc
        return self._folder_to_response(folder)

    async def set_default_folder(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        folder_id: int,
    ) -> JobCollectionFolderResponse:
        """把当前用户某个 active 收藏夹设置为默认收藏夹。"""

        try:
            folder = await self.folder_repository.get_user_folder(
                db,
                user_id=user_id,
                folder_id=folder_id,
            )
            if folder is None:
                raise JobCollectionFolderNotFoundError()
            await self.folder_repository.clear_default_folders(
                db,
                user_id=user_id,
                exclude_folder_id=folder.id,
            )
            folder = await self.folder_repository.update_folder(
                db,
                folder=folder,
                values={"is_default": True},
            )
        except IntegrityError as exc:
            raise DefaultJobCollectionFolderConflictError() from exc
        return self._folder_to_response(folder)

    async def archive_folder(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        folder_id: int,
    ) -> JobCollectionFolderResponse:
        """归档收藏夹，并把其中收藏移回默认未分组。"""

        folder = await self.folder_repository.get_user_folder(
            db,
            user_id=user_id,
            folder_id=folder_id,
        )
        if folder is None:
            raise JobCollectionFolderNotFoundError()
        if folder.is_default:
            raise DefaultJobCollectionFolderCannotArchiveError()
        default_folder = await self.folder_repository.get_or_create_default_folder(
            db,
            user_id=user_id,
        )
        await self.folder_repository.move_collections_to_default_folder(
            db,
            user_id=user_id,
            folder_id=folder_id,
            default_folder_id=default_folder.id,
        )
        folder = await self.folder_repository.archive_folder(db, folder=folder)
        log_app_event(
            logger,
            "Job collection folder archived",
            extra={
                "event": "job_collections.folder_archived",
                "user_id": user_id,
                "folder_id": folder.id,
                "default_folder_id": default_folder.id,
            },
        )
        return self._folder_to_response(folder)

    async def collect_job(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        payload: JobCollectionCreateCommand,
    ) -> JobCollectionResponse:
        """新增或恢复当前用户岗位收藏。"""

        await self._ensure_job_exists(db, job_post_id=payload.job_post_id)
        folder_id = await self._resolve_folder_id(
            db,
            user_id=user_id,
            folder_id=payload.folder_id,
        )
        create_values = {
            "folder_id": folder_id,
            "note": payload.note,
        }
        update_values = self._build_update_values(payload, exclude={"job_post_id"})
        update_values["folder_id"] = folder_id
        collection = await self.collection_repository.upsert_active_collection(
            db,
            user_id=user_id,
            job_post_id=payload.job_post_id,
            create_values=create_values,
            update_values=update_values,
        )
        log_app_event(
            logger,
            "Job collected or restored",
            extra={
                "event": "job_collections.collected",
                "user_id": user_id,
                "collection_id": collection.id,
                "job_post_id": collection.job_post_id,
                "folder_id": collection.folder_id,
                "status": collection.status.value,
            },
        )
        return self._collection_to_response(collection)

    async def list_collections(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: JobCollectionListQuery,
    ) -> JobCollectionListResponse:
        """分页查询当前用户岗位收藏。"""

        if params.folder_id is not None:
            await self._ensure_folder_owned(db, user_id=user_id, folder_id=params.folder_id)
        collections = await self.collection_repository.list_user_collections(
            db,
            user_id=user_id,
            params=params,
        )
        page_items, has_next = trim_page_items(
            collections,
            page_size=params.page_size,
        )
        return JobCollectionListResponse(
            items=[self._collection_to_response(collection) for collection in page_items],
            page=params.page,
            page_size=params.page_size,
            total=None,
            has_next=has_next,
        )

    async def update_collection(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        collection_id: int,
        payload: JobCollectionUpdateCommand,
    ) -> JobCollectionResponse:
        """更新当前用户 active 岗位收藏。"""

        collection = await self.collection_repository.get_user_collection(
            db,
            user_id=user_id,
            collection_id=collection_id,
        )
        if collection is None:
            raise JobCollectionNotFoundError()
        values = self._build_update_values(payload)
        if "folder_id" in payload.fields_set:
            values["folder_id"] = await self._resolve_folder_id(
                db,
                user_id=user_id,
                folder_id=payload.folder_id,
            )
        if values:
            collection = await self.collection_repository.update_collection(
                db,
                collection=collection,
                values=values,
            )
            log_app_event(
                logger,
                "Job collection updated",
                extra={
                    "event": "job_collections.updated",
                    "user_id": user_id,
                    "collection_id": collection.id,
                    "job_post_id": collection.job_post_id,
                    "updated_fields": sorted(values.keys()),
                },
            )
        return self._collection_to_response(collection)

    async def remove_collection(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        collection_id: int,
    ) -> JobCollectionResponse:
        """软取消当前用户岗位收藏。"""

        collection = await self.collection_repository.remove_collection(
            db,
            user_id=user_id,
            collection_id=collection_id,
        )
        if collection is None:
            raise JobCollectionNotFoundError()
        log_app_event(
            logger,
            "Job collection removed",
            extra={
                "event": "job_collections.removed",
                "user_id": user_id,
                "collection_id": collection.id,
                "job_post_id": collection.job_post_id,
                "status": collection.status.value,
            },
        )
        return self._collection_to_response(collection)

    async def _ensure_job_exists(self, db: AsyncSession, *, job_post_id: int) -> None:
        if not await self.collection_repository.job_post_exists(db, job_post_id=job_post_id):
            raise JobPostForCollectionNotFoundError()

    async def _resolve_folder_id(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        folder_id: int | None,
    ) -> int:
        """把空收藏夹参数解析为当前用户默认收藏夹 ID。"""

        if folder_id is None:
            default_folder = await self.folder_repository.get_or_create_default_folder(
                db,
                user_id=user_id,
            )
            return default_folder.id

        await self._ensure_folder_owned(db, user_id=user_id, folder_id=folder_id)
        return folder_id

    async def _ensure_folder_owned(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        folder_id: int | None,
    ) -> None:
        if folder_id is None:
            return
        folder = await self.folder_repository.get_user_folder(
            db,
            user_id=user_id,
            folder_id=folder_id,
        )
        if folder is None:
            raise JobCollectionFolderNotFoundError()

    @staticmethod
    def _build_update_values(
        payload: (
            JobCollectionFolderUpdateCommand
            | JobCollectionUpdateCommand
            | JobCollectionCreateCommand
        ),
        *,
        exclude: set[str] | None = None,
    ) -> dict[str, object]:
        values: dict[str, object] = {}
        excluded_fields = exclude or set()
        field_names = payload.fields_set or _changed_dataclass_fields(payload)
        for field_name in field_names:
            if field_name in excluded_fields:
                continue
            values[field_name] = getattr(payload, field_name)
        return values

    @staticmethod
    def _folder_to_response(folder: JobCollectionFolder) -> JobCollectionFolderResponse:
        return JobCollectionFolderResponse(
            id=folder.id,
            user_id=folder.user_id,
            name=folder.name,
            status=folder.status,
            is_default=folder.is_default,
            sort_order=folder.sort_order,
            archived_at=folder.archived_at,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
        )

    @staticmethod
    def _collection_to_response(collection: JobCollection) -> JobCollectionResponse:
        return JobCollectionResponse(
            id=collection.id,
            user_id=collection.user_id,
            job_post_id=collection.job_post_id,
            folder_id=collection.folder_id,
            status=collection.status,
            note=collection.note,
            collected_at=collection.collected_at,
            removed_at=collection.removed_at,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )


def build_job_collection_service() -> JobCollectionService:
    """组装岗位收藏 service 的默认依赖。"""

    return JobCollectionService(
        folder_repository=JobCollectionFolderRepository(),
        collection_repository=JobCollectionRepository(),
    )


def _changed_dataclass_fields(payload: object) -> frozenset[str]:
    """推断直接构造 command 时显式改变过的字段。"""

    changed_fields: set[str] = set()
    for field_name, field_info in payload.__dataclass_fields__.items():  # type: ignore[attr-defined]
        if field_name == "fields_set" or field_info.default is MISSING:
            continue
        if getattr(payload, field_name) != field_info.default:
            changed_fields.add(field_name)
    return frozenset(changed_fields)
