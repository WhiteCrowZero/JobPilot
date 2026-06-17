from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.job_collections.contracts import (
    JobCollectionCreateCommand as JobCollectionCreate,
)
from job_pilot.modules.job_collections.contracts import (
    JobCollectionFolderCreateCommand as JobCollectionFolderCreate,
)
from job_pilot.modules.job_collections.contracts import (
    JobCollectionFolderUpdateCommand as JobCollectionFolderUpdate,
)
from job_pilot.modules.job_collections.contracts import (
    JobCollectionListQuery as JobCollectionListParams,
)
from job_pilot.modules.job_collections.contracts import (
    JobCollectionUpdateCommand as JobCollectionUpdate,
)
from job_pilot.modules.job_collections.enums import (
    JobCollectionFolderStatus,
    JobCollectionStatus,
)
from job_pilot.modules.job_collections.exceptions import (
    DefaultJobCollectionFolderCannotArchiveError,
    JobCollectionFolderNameConflictError,
    JobCollectionFolderNotFoundError,
    JobCollectionNotFoundError,
    JobPostForCollectionNotFoundError,
)
from tests.helpers.builders import (
    create_test_user,
    seed_test_job_post,
)
from tests.helpers.database import truncate_workbench_tables


@pytest.mark.asyncio
async def test_collection_folder_lifecycle_moves_collections_to_default(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)

        folder = await pilot.workbench.create_collection_folder(
            user_id=user.id,
            payload=JobCollectionFolderCreate(name="Backend", sort_order=1),
        )
        updated_folder = await pilot.workbench.update_collection_folder(
            user_id=user.id,
            folder_id=folder.id,
            payload=JobCollectionFolderUpdate(name="Backend Focus", sort_order=2),
        )
        collected = await pilot.workbench.collect_job(
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id, folder_id=folder.id),
        )
        archived_folder = await pilot.workbench.archive_collection_folder(
            user_id=user.id,
            folder_id=folder.id,
        )
        folders = await pilot.workbench.list_collection_folders(user_id=user.id)
        default_folder = next(item for item in folders if item.is_default)
        collections = await pilot.workbench.list_collections(
            user_id=user.id,
            params=JobCollectionListParams(page=1, page_size=10),
        )

        with pytest.raises(DefaultJobCollectionFolderCannotArchiveError):
            await pilot.workbench.archive_collection_folder(
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
async def test_collect_job_restore_preserves_old_note_when_note_not_provided(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)

        created = await pilot.workbench.collect_job(
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id, note="Old note"),
        )
        removed = await pilot.workbench.remove_collection(
            user_id=user.id,
            collection_id=created.id,
        )
        restored = await pilot.workbench.collect_job(
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id),
        )

        assert removed.status == JobCollectionStatus.REMOVED
        assert restored.id == created.id
        assert restored.status == JobCollectionStatus.ACTIVE
        assert restored.removed_at is None
        assert restored.note == "Old note"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_collection_folder_name_conflict_returns_domain_error(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        backend_folder = await pilot.workbench.create_collection_folder(
            user_id=user.id,
            payload=JobCollectionFolderCreate(name="Backend"),
        )
        frontend_folder = await pilot.workbench.create_collection_folder(
            user_id=user.id,
            payload=JobCollectionFolderCreate(name="Frontend"),
        )

        with pytest.raises(JobCollectionFolderNameConflictError) as create_exc:
            await pilot.workbench.create_collection_folder(
                user_id=user.id,
                payload=JobCollectionFolderCreate(name=backend_folder.name),
            )

        with pytest.raises(JobCollectionFolderNameConflictError) as update_exc:
            await pilot.workbench.update_collection_folder(
                user_id=user.id,
                folder_id=frontend_folder.id,
                payload=JobCollectionFolderUpdate(name=backend_folder.name),
            )

        assert create_exc.value.code == "JOB_COLLECTION_FOLDER_NAME_CONFLICT"
        assert update_exc.value.code == "JOB_COLLECTION_FOLDER_NAME_CONFLICT"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_collect_job_restore_overwrites_explicit_note(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)

        created = await pilot.workbench.collect_job(
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id, note="Old note"),
        )
        await pilot.workbench.remove_collection(
            user_id=user.id,
            collection_id=created.id,
        )
        restored = await pilot.workbench.collect_job(
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id, note="New note"),
        )

        assert restored.id == created.id
        assert restored.status == JobCollectionStatus.ACTIVE
        assert restored.removed_at is None
        assert restored.note == "New note"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_collect_job_uses_default_folder_and_restores_removed_collection(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)

        created = await pilot.workbench.collect_job(
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id, note="Interesting"),
        )
        folders = await pilot.workbench.list_collection_folders(user_id=user.id)
        default_folder = next(item for item in folders if item.is_default)
        removed = await pilot.workbench.remove_collection(
            user_id=user.id,
            collection_id=created.id,
        )
        restored = await pilot.workbench.collect_job(
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
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)
        backend_folder = await pilot.workbench.create_collection_folder(
            user_id=user.id,
            payload=JobCollectionFolderCreate(name="Backend"),
        )
        initial_folders = await pilot.workbench.list_collection_folders(user_id=user.id)
        old_default_folder = next(item for item in initial_folders if item.is_default)

        new_default_folder = await pilot.workbench.set_default_collection_folder(
            user_id=user.id,
            folder_id=backend_folder.id,
        )
        collected = await pilot.workbench.collect_job(
            user_id=user.id,
            payload=JobCollectionCreate(job_post_id=job_post.id),
        )
        folders = await pilot.workbench.list_collection_folders(user_id=user.id)
        archived_old_default = await pilot.workbench.archive_collection_folder(
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
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        job_post = await seed_test_job_post(db_session)
        other_folder = await pilot.workbench.create_collection_folder(
            user_id=other_user.id,
            payload=JobCollectionFolderCreate(name="Other Folder"),
        )
        user_id = user.id
        job_post_id = job_post.id
        other_folder_id = other_folder.id

        with pytest.raises(JobPostForCollectionNotFoundError):
            await pilot.workbench.collect_job(
                user_id=user_id,
                payload=JobCollectionCreate(job_post_id=999_999),
            )

        with pytest.raises(JobCollectionFolderNotFoundError):
            await pilot.workbench.collect_job(
                user_id=user_id,
                payload=JobCollectionCreate(job_post_id=job_post_id, folder_id=other_folder_id),
            )
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_update_remove_and_list_collections_are_user_isolated(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        backend_job = await seed_test_job_post(db_session, title="Backend Engineer")
        data_job = await seed_test_job_post(db_session, title="Data Engineer")
        folder = await pilot.workbench.create_collection_folder(
            user_id=owner.id,
            payload=JobCollectionFolderCreate(name="Backend"),
        )
        backend_collection = await pilot.workbench.collect_job(
            user_id=owner.id,
            payload=JobCollectionCreate(job_post_id=backend_job.id, folder_id=folder.id),
        )
        await pilot.workbench.collect_job(
            user_id=owner.id,
            payload=JobCollectionCreate(job_post_id=data_job.id),
        )
        folders = await pilot.workbench.list_collection_folders(user_id=owner.id)
        default_folder = next(item for item in folders if item.is_default)

        updated = await pilot.workbench.update_collection(
            user_id=owner.id,
            collection_id=backend_collection.id,
            payload=JobCollectionUpdate(
                note="High priority",
                folder_id=None,
                fields_set=frozenset({"note", "folder_id"}),
            ),
        )
        filtered = await pilot.workbench.list_collections(
            user_id=owner.id,
            params=JobCollectionListParams(folder_id=folder.id, page=1, page_size=10),
        )
        removed = await pilot.workbench.remove_collection(
            user_id=owner.id,
            collection_id=backend_collection.id,
        )
        active_list = await pilot.workbench.list_collections(
            user_id=owner.id,
            params=JobCollectionListParams(page=1, page_size=10),
        )
        removed_list = await pilot.workbench.list_collections(
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
            await pilot.workbench.update_collection(
                user_id=other_user.id,
                collection_id=backend_collection.id,
                payload=JobCollectionUpdate(note="Cross user"),
            )
    finally:
        await truncate_workbench_tables(db_session)
