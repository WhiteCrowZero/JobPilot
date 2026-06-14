from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.job_collections.enums import (
    JobCollectionFolderStatus,
    JobCollectionStatus,
)
from job_pilot.modules.job_collections.exceptions import (
    DefaultJobCollectionFolderCannotArchiveError,
    JobCollectionFolderNotFoundError,
    JobCollectionNotFoundError,
    JobPostForCollectionNotFoundError,
)
from job_pilot.modules.job_collections.schemas import (
    JobCollectionCreate,
    JobCollectionFolderCreate,
    JobCollectionFolderUpdate,
    JobCollectionListParams,
    JobCollectionUpdate,
)
from job_pilot.modules.job_collections.service import build_job_collection_service
from tests.helpers.workbench import (
    create_test_user,
    seed_test_job_post,
    truncate_workbench_tables,
)


@pytest.mark.asyncio
async def test_collection_folder_lifecycle_moves_collections_to_default(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    service = build_job_collection_service()

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)

        folder = await service.create_folder(
            db_session,
            user_id=user.id,
            payload=JobCollectionFolderCreate(name="Backend", sort_order=1),
        )
        updated_folder = await service.update_folder(
            db_session,
            user_id=user.id,
            folder_id=folder.id,
            payload=JobCollectionFolderUpdate(name="Backend Focus", sort_order=2),
        )
        collected = await service.collect_job(
            db_session,
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id, folder_id=folder.id),
        )
        archived_folder = await service.archive_folder(
            db_session,
            user_id=user.id,
            folder_id=folder.id,
        )
        folders = await service.list_folders(db_session, user_id=user.id)
        default_folder = next(item for item in folders if item.is_default)
        collections = await service.list_collections(
            db_session,
            user_id=user.id,
            params=JobCollectionListParams(page=1, page_size=10),
        )

        with pytest.raises(DefaultJobCollectionFolderCannotArchiveError):
            await service.archive_folder(
                db_session,
                user_id=user.id,
                folder_id=default_folder.id,
            )

        assert updated_folder.name == "Backend Focus"
        assert updated_folder.sort_order == 2
        assert updated_folder.is_default is False
        assert collected.folder_id == folder.id
        assert archived_folder.status == JobCollectionFolderStatus.ARCHIVED
        assert archived_folder.archived_at is not None
        assert [item.folder_id for item in collections.items] == [default_folder.id]
        assert [item.name for item in folders] == ["默认收藏夹"]
        assert default_folder.is_default is True
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_collect_job_uses_default_folder_and_restores_removed_collection(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    service = build_job_collection_service()

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)

        created = await service.collect_job(
            db_session,
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id, note="Interesting"),
        )
        folders = await service.list_folders(db_session, user_id=user.id)
        default_folder = next(item for item in folders if item.is_default)
        removed = await service.remove_collection(
            db_session,
            user_id=user.id,
            collection_id=created.id,
        )
        restored = await service.collect_job(
            db_session,
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id),
        )

        assert created.status == JobCollectionStatus.ACTIVE
        assert created.folder_id == default_folder.id
        assert removed.status == JobCollectionStatus.REMOVED
        assert removed.removed_at is not None
        assert removed.folder_id == default_folder.id
        assert restored.id == created.id
        assert restored.status == JobCollectionStatus.ACTIVE
        assert restored.removed_at is None
        assert restored.folder_id == default_folder.id
        assert restored.note == "Interesting"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_update_folder_can_switch_default_folder(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    service = build_job_collection_service()

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)
        backend_folder = await service.create_folder(
            db_session,
            user_id=user.id,
            payload=JobCollectionFolderCreate(name="Backend"),
        )
        initial_folders = await service.list_folders(db_session, user_id=user.id)
        old_default_folder = next(item for item in initial_folders if item.is_default)

        new_default_folder = await service.update_folder(
            db_session,
            user_id=user.id,
            folder_id=backend_folder.id,
            payload=JobCollectionFolderUpdate(is_default=True),
        )
        collected = await service.collect_job(
            db_session,
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id),
        )
        folders = await service.list_folders(db_session, user_id=user.id)
        archived_old_default = await service.archive_folder(
            db_session,
            user_id=user.id,
            folder_id=old_default_folder.id,
        )

        assert new_default_folder.is_default is True
        assert collected.folder_id == backend_folder.id
        assert [item.id for item in folders if item.is_default] == [backend_folder.id]
        assert archived_old_default.status == JobCollectionFolderStatus.ARCHIVED
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_collect_job_rejects_missing_job_and_invalid_folder(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    service = build_job_collection_service()

    try:
        user = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        job_post = await seed_test_job_post(db_session)
        other_folder = await service.create_folder(
            db_session,
            user_id=other_user.id,
            payload=JobCollectionFolderCreate(name="Other Folder"),
        )
        user_id = user.id
        job_post_id = job_post.id
        other_folder_id = other_folder.id

        with pytest.raises(JobPostForCollectionNotFoundError):
            await service.collect_job(
                db_session,
                user_id=user_id,
                payload=JobCollectionCreate(job_post_id=999_999),
            )

        with pytest.raises(JobCollectionFolderNotFoundError):
            await service.collect_job(
                db_session,
                user_id=user_id,
                payload=JobCollectionCreate(job_post_id=job_post_id, folder_id=other_folder_id),
            )
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_update_remove_and_list_collections_are_user_isolated(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    service = build_job_collection_service()

    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        backend_job = await seed_test_job_post(db_session, title="Backend Engineer")
        data_job = await seed_test_job_post(db_session, title="Data Engineer")
        folder = await service.create_folder(
            db_session,
            user_id=owner.id,
            payload=JobCollectionFolderCreate(name="Backend"),
        )
        backend_collection = await service.collect_job(
            db_session,
            user_id=owner.id,
            payload=JobCollectionCreate(job_post_id=backend_job.id, folder_id=folder.id),
        )
        await service.collect_job(
            db_session,
            user_id=owner.id,
            payload=JobCollectionCreate(job_post_id=data_job.id),
        )
        folders = await service.list_folders(db_session, user_id=owner.id)
        default_folder = next(item for item in folders if item.is_default)

        updated = await service.update_collection(
            db_session,
            user_id=owner.id,
            collection_id=backend_collection.id,
            payload=JobCollectionUpdate(note="High priority", folder_id=None),
        )
        filtered = await service.list_collections(
            db_session,
            user_id=owner.id,
            params=JobCollectionListParams(folder_id=folder.id, page=1, page_size=10),
        )
        removed = await service.remove_collection(
            db_session,
            user_id=owner.id,
            collection_id=backend_collection.id,
        )
        active_list = await service.list_collections(
            db_session,
            user_id=owner.id,
            params=JobCollectionListParams(page=1, page_size=10),
        )
        removed_list = await service.list_collections(
            db_session,
            user_id=owner.id,
            params=JobCollectionListParams(include_removed=True, page=1, page_size=10),
        )

        assert updated.note == "High priority"
        assert updated.folder_id == default_folder.id
        assert filtered.items == []
        assert removed.status == JobCollectionStatus.REMOVED
        assert [item.job_post_id for item in active_list.items] == [data_job.id]
        assert {item.job_post_id for item in removed_list.items} == {backend_job.id, data_job.id}

        with pytest.raises(JobCollectionNotFoundError):
            await service.update_collection(
                db_session,
                user_id=other_user.id,
                collection_id=backend_collection.id,
                payload=JobCollectionUpdate(note="Cross user"),
            )
    finally:
        await truncate_workbench_tables(db_session)
