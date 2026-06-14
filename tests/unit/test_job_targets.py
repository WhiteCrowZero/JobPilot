from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.job_collections.schemas import JobCollectionCreate
from job_pilot.modules.job_collections.service import build_job_collection_service
from job_pilot.modules.job_targets.enums import JobTargetStatus
from job_pilot.modules.job_targets.exceptions import (
    JobPostForTargetNotFoundError,
    JobTargetNotFoundError,
    JobTargetSourceCollectionInvalidError,
)
from job_pilot.modules.job_targets.schemas import (
    JobTargetCreate,
    JobTargetListParams,
    JobTargetUpdate,
)
from job_pilot.modules.job_targets.service import build_job_target_service
from tests.helpers.workbench import (
    create_test_user,
    seed_test_job_post,
    truncate_workbench_tables,
)


@pytest.mark.asyncio
async def test_create_target_directly_and_restore_completed_target(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    service = build_job_target_service()

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session)

        created = await service.create_target(
            db_session,
            user_id=user.id,
            payload=JobTargetCreate(
                job_post_id=job_post.id,
                priority=1,
                is_primary=True,
                note="Prepare system design",
                target_date=date(2026, 7, 1),
            ),
        )
        completed = await service.update_target(
            db_session,
            user_id=user.id,
            target_id=created.id,
            payload=JobTargetUpdate(status=JobTargetStatus.COMPLETED),
        )
        updated_completed = await service.update_target(
            db_session,
            user_id=user.id,
            target_id=created.id,
            payload=JobTargetUpdate(note="Keep completion time"),
        )
        restored = await service.create_target(
            db_session,
            user_id=user.id,
            payload=JobTargetCreate(job_post_id=job_post.id),
        )

        assert created.status == JobTargetStatus.ACTIVE
        assert created.priority == 1
        assert created.is_primary is True
        assert created.target_date == date(2026, 7, 1)
        assert completed.status == JobTargetStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.is_primary is False
        assert updated_completed.completed_at == completed.completed_at
        assert updated_completed.note == "Keep completion time"
        assert restored.id == created.id
        assert restored.status == JobTargetStatus.ACTIVE
        assert restored.completed_at is None
        assert restored.archived_at is None
        assert restored.note == "Keep completion time"

        with pytest.raises(JobPostForTargetNotFoundError):
            await service.create_target(
                db_session,
                user_id=user.id,
                payload=JobTargetCreate(job_post_id=999_999),
            )
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_create_target_validates_source_collection_ownership_and_job(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    collection_service = build_job_collection_service()
    target_service = build_job_target_service()

    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        backend_job = await seed_test_job_post(db_session, title="Backend Engineer")
        data_job = await seed_test_job_post(db_session, title="Data Engineer")
        matching_collection = await collection_service.collect_job(
            db_session,
            user_id=owner.id,
            payload=JobCollectionCreate(job_post_id=backend_job.id),
        )
        mismatched_collection = await collection_service.collect_job(
            db_session,
            user_id=owner.id,
            payload=JobCollectionCreate(job_post_id=data_job.id),
        )
        other_collection = await collection_service.collect_job(
            db_session,
            user_id=other_user.id,
            payload=JobCollectionCreate(job_post_id=backend_job.id),
        )
        owner_id = owner.id
        backend_job_id = backend_job.id
        matching_collection_id = matching_collection.id
        mismatched_collection_id = mismatched_collection.id
        other_collection_id = other_collection.id

        created = await target_service.create_target(
            db_session,
            user_id=owner_id,
            payload=JobTargetCreate(
                job_post_id=backend_job_id,
                source_collection_id=matching_collection_id,
            ),
        )

        assert created.source_collection_id == matching_collection_id

        completed = await target_service.update_target(
            db_session,
            user_id=owner_id,
            target_id=created.id,
            payload=JobTargetUpdate(status=JobTargetStatus.COMPLETED),
        )
        restored_without_source = await target_service.create_target(
            db_session,
            user_id=owner_id,
            payload=JobTargetCreate(job_post_id=backend_job_id),
        )

        assert completed.source_collection_id == matching_collection_id
        assert restored_without_source.id == created.id
        assert restored_without_source.source_collection_id is None

        with pytest.raises(JobTargetSourceCollectionInvalidError):
            await target_service.create_target(
                db_session,
                user_id=owner_id,
                payload=JobTargetCreate(
                    job_post_id=backend_job_id,
                    source_collection_id=mismatched_collection_id,
                ),
            )

        with pytest.raises(JobTargetSourceCollectionInvalidError):
            await target_service.create_target(
                db_session,
                user_id=owner_id,
                payload=JobTargetCreate(
                    job_post_id=backend_job_id,
                    source_collection_id=other_collection_id,
                ),
            )
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_primary_target_replacement_and_status_lifecycle(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    service = build_job_target_service()

    try:
        user = await create_test_user(db_session)
        backend_job = await seed_test_job_post(db_session, title="Backend Engineer")
        data_job = await seed_test_job_post(db_session, title="Data Engineer")
        backend_target = await service.create_target(
            db_session,
            user_id=user.id,
            payload=JobTargetCreate(job_post_id=backend_job.id, priority=2, is_primary=True),
        )
        data_target = await service.create_target(
            db_session,
            user_id=user.id,
            payload=JobTargetCreate(job_post_id=data_job.id, priority=1, is_primary=True),
        )

        current_targets = await service.list_targets(
            db_session,
            user_id=user.id,
            params=JobTargetListParams(page=1, page_size=10),
        )
        paused = await service.update_target(
            db_session,
            user_id=user.id,
            target_id=backend_target.id,
            payload=JobTargetUpdate(status=JobTargetStatus.PAUSED, is_primary=True),
        )
        completed = await service.update_target(
            db_session,
            user_id=user.id,
            target_id=paused.id,
            payload=JobTargetUpdate(status=JobTargetStatus.COMPLETED),
        )
        reactivated = await service.update_target(
            db_session,
            user_id=user.id,
            target_id=paused.id,
            payload=JobTargetUpdate(status=JobTargetStatus.ACTIVE),
        )
        archived = await service.archive_target(
            db_session,
            user_id=user.id,
            target_id=data_target.id,
        )
        default_list = await service.list_targets(
            db_session,
            user_id=user.id,
            params=JobTargetListParams(page=1, page_size=10),
        )
        archived_list = await service.list_targets(
            db_session,
            user_id=user.id,
            params=JobTargetListParams(
                statuses=[JobTargetStatus.ARCHIVED],
                page=1,
                page_size=10,
            ),
        )

        assert [item.job_post_id for item in current_targets.items] == [
            data_job.id,
            backend_job.id,
        ]
        assert current_targets.items[0].is_primary is True
        assert current_targets.items[1].is_primary is False
        assert paused.status == JobTargetStatus.PAUSED
        assert paused.is_primary is True
        assert completed.status == JobTargetStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.is_primary is False
        assert reactivated.status == JobTargetStatus.ACTIVE
        assert reactivated.completed_at is None
        assert reactivated.archived_at is None
        assert archived.status == JobTargetStatus.ARCHIVED
        assert archived.archived_at is not None
        assert archived.is_primary is False
        assert [item.job_post_id for item in default_list.items] == [backend_job.id]
        assert [item.job_post_id for item in archived_list.items] == [data_job.id]
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_update_target_hides_other_users_target(
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)
    service = build_job_target_service()

    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        job_post = await seed_test_job_post(db_session)
        target = await service.create_target(
            db_session,
            user_id=owner.id,
            payload=JobTargetCreate(job_post_id=job_post.id),
        )

        with pytest.raises(JobTargetNotFoundError):
            await service.update_target(
                db_session,
                user_id=other_user.id,
                target_id=target.id,
                payload=JobTargetUpdate(note="Cross user"),
            )
    finally:
        await truncate_workbench_tables(db_session)
