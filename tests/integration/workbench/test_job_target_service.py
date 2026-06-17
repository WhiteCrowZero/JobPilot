from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.job_targets.enums import JobTargetStatus
from job_pilot.modules.job_targets.exceptions import (
    JobPostForTargetNotFoundError,
    JobTargetNotFoundError,
)
from job_pilot.modules.job_targets.schemas import (
    JobTargetCreate,
    JobTargetListParams,
    JobTargetUpdate,
)
from tests.helpers.builders import create_test_user, seed_test_job_post
from tests.helpers.database import truncate_workbench_tables


@pytest.mark.asyncio
async def test_target_public_api_create_primary_update_archive_and_restore(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """通过公开库入口覆盖目标岗位核心状态流转。"""

    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session, display_name="Target API User")
        backend_job = await seed_test_job_post(db_session, title="Backend Engineer")
        data_job = await seed_test_job_post(db_session, title="Data Engineer")

        backend_target = await pilot.workbench.create_target(
            user_id=user.id,
            payload=JobTargetCreate(
                job_post_id=backend_job.id,
                priority=2,
                is_primary=True,
                note="Backend target",
            ),
        )
        data_target = await pilot.workbench.create_target(
            user_id=user.id,
            payload=JobTargetCreate(
                job_post_id=data_job.id,
                priority=1,
                is_primary=True,
            ),
        )
        target_list = await pilot.workbench.list_targets(
            user_id=user.id,
            params=JobTargetListParams(page=1, page_size=10),
        )
        completed = await pilot.workbench.update_target(
            user_id=user.id,
            target_id=data_target.id,
            payload=JobTargetUpdate(status=JobTargetStatus.COMPLETED),
        )
        archived = await pilot.workbench.archive_target(
            user_id=user.id,
            target_id=backend_target.id,
        )
        default_list = await pilot.workbench.list_targets(
            user_id=user.id,
            params=JobTargetListParams(page=1, page_size=10),
        )
        archived_list = await pilot.workbench.list_targets(
            user_id=user.id,
            params=JobTargetListParams(
                statuses=[JobTargetStatus.ARCHIVED],
                page=1,
                page_size=10,
            ),
        )
        restored = await pilot.workbench.create_target(
            user_id=user.id,
            payload=JobTargetCreate(job_post_id=backend_job.id),
        )

        assert backend_target.job_post_id == backend_job.id
        assert backend_target.is_primary is True
        assert data_target.job_post_id == data_job.id
        assert data_target.is_primary is True

        assert [item.job_post_id for item in target_list.items] == [
            data_job.id,
            backend_job.id,
        ]
        assert target_list.items[0].is_primary is True
        assert target_list.items[1].is_primary is False

        assert completed.status == JobTargetStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.is_primary is False

        assert archived.status == JobTargetStatus.ARCHIVED
        assert archived.archived_at is not None
        assert archived.is_primary is False

        assert default_list.items == []
        assert [item.job_post_id for item in archived_list.items] == [backend_job.id]

        assert restored.id == backend_target.id
        assert restored.status == JobTargetStatus.ACTIVE
        assert restored.archived_at is None
        assert restored.note == "Backend target"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_target_public_api_rejects_missing_job_and_hides_cross_user_target(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """通过公开库入口验证缺失岗位和跨用户隔离。"""

    await truncate_workbench_tables(db_session)

    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        job_post = await seed_test_job_post(db_session)

        with pytest.raises(JobPostForTargetNotFoundError):
            await pilot.workbench.create_target(
                user_id=owner.id,
                payload=JobTargetCreate(job_post_id=999_999),
            )

        created = await pilot.workbench.create_target(
            user_id=owner.id,
            payload=JobTargetCreate(job_post_id=job_post.id),
        )

        with pytest.raises(JobTargetNotFoundError):
            await pilot.workbench.update_target(
                user_id=other_user.id,
                target_id=created.id,
                payload=JobTargetUpdate(note="Cross user"),
            )

        other_list = await pilot.workbench.list_targets(
            user_id=other_user.id,
            params=JobTargetListParams(page=1, page_size=10),
        )

        assert other_list.items == []
    finally:
        await truncate_workbench_tables(db_session)
