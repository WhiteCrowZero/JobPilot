from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.core.exceptions import ValidationError
from job_pilot.modules.job_match.enums import JobMatchAnalysisStatus, JobMatchSkillStatus
from job_pilot.modules.job_match.exceptions import (
    JobPostForMatchNotFoundError,
    JobTargetForMatchNotFoundError,
)
from job_pilot.modules.job_targets.contracts import JobTargetCreateCommand as JobTargetCreate
from job_pilot.modules.user_skills.contracts import UserSkillUpsertCommand as UserSkillUpsert
from tests.helpers.builders import (
    create_test_user,
    seed_test_job_post,
    seed_test_job_post_skills,
    seed_test_skill,
    seed_test_skills,
)
from tests.helpers.database import truncate_workbench_tables


@pytest.mark.asyncio
async def test_analyze_job_skill_coverage_returns_intersection_counts(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        python, redis, mysql = await seed_test_skills(db_session, ["Python", "Redis", "MySQL"])
        job_post = await seed_test_job_post(db_session, title="Backend Engineer")
        await seed_test_job_post_skills(
            db_session,
            job_post_id=job_post.id,
            skill_ids=[python.id, redis.id, mysql.id],
        )
        await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(skill_id=python.id, proficiency_level=4),
        )
        await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(skill_id=redis.id, proficiency_level=2),
        )

        response = await pilot.workbench.analyze_job_skill_coverage(
            user_id=user.id,
            job_post_id=job_post.id,
            required_level=3,
        )

        assert response.analysis_status == JobMatchAnalysisStatus.ANALYZABLE
        assert response.required_skill_count == 3
        assert response.matched_count == 1
        assert response.weak_count == 1
        assert response.missing_count == 1
        assert response.coverage_score == 0.3333
        assert [item.skill_name for item in response.matched_skills] == ["Python"]
        assert [item.skill_name for item in response.weak_skills] == ["Redis"]
        assert [item.skill_name for item in response.missing_skills] == ["MySQL"]
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_job_skill_coverage_does_not_score_empty_job_skills(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        job_post = await seed_test_job_post(db_session, title="Backend Engineer")

        response = await pilot.workbench.analyze_job_skill_coverage(
            user_id=user.id,
            job_post_id=job_post.id,
        )

        assert response.analysis_status == JobMatchAnalysisStatus.NO_JOB_SKILL_DATA
        assert response.coverage_score is None
        assert response.required_skill_count == 0
        assert response.matched_skills == []
        assert response.weak_skills == []
        assert response.missing_skills == []
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_job_skill_coverage_raises_for_missing_job_post(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)

        with pytest.raises(JobPostForMatchNotFoundError):
            await pilot.workbench.analyze_job_skill_coverage(
                user_id=user.id,
                job_post_id=999_999,
            )
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_archived_user_skill_is_treated_as_missing(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        redis = await seed_test_skill(db_session, "Redis")
        job_post = await seed_test_job_post(db_session, title="Backend Engineer")
        await seed_test_job_post_skills(
            db_session,
            job_post_id=job_post.id,
            skill_ids=[redis.id],
        )
        await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(skill_id=redis.id, proficiency_level=5),
        )
        await pilot.workbench.archive_user_skill(
            user_id=user.id,
            skill_id=redis.id,
        )

        response = await pilot.workbench.analyze_job_skill_coverage(
            user_id=user.id,
            job_post_id=job_post.id,
        )

        assert response.matched_count == 0
        assert response.missing_count == 1
        assert response.missing_skills[0].skill_name == "Redis"
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_target_skill_coverage_hides_other_users_target(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        job_post = await seed_test_job_post(db_session, title="Backend Engineer")
        target = await pilot.workbench.create_target(
            user_id=owner.id,
            payload=JobTargetCreate(job_post_id=job_post.id),
        )

        with pytest.raises(JobTargetForMatchNotFoundError):
            await pilot.workbench.analyze_target_skill_coverage(
                user_id=other_user.id,
                target_id=target.id,
            )
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_target_skill_summary_returns_empty_result_without_targets(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)

        response = await pilot.workbench.analyze_target_skill_summary(
            user_id=user.id,
        )

        assert response.target_count == 0
        assert response.primary_target_id is None
        assert response.primary_job_post_id is None
        assert response.primary_target_skill_count == 0
        assert response.other_target_count == 0
        assert response.skill_count == 0
        assert response.items == []
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_target_skill_summary_rejects_invalid_limit(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)

        with pytest.raises(ValidationError):
            await pilot.workbench.analyze_target_skill_summary(
                user_id=user.id,
                limit=0,
            )

        with pytest.raises(ValidationError):
            await pilot.workbench.analyze_target_skill_summary(
                user_id=user.id,
                limit=101,
            )
    finally:
        await truncate_workbench_tables(db_session)


@pytest.mark.asyncio
async def test_analyze_target_skill_summary_sorts_by_target_count(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_workbench_tables(db_session)

    try:
        user = await create_test_user(db_session)
        python, redis, mysql = await seed_test_skills(db_session, ["Python", "Redis", "MySQL"])
        first_job = await seed_test_job_post(db_session, title="Backend Engineer")
        second_job = await seed_test_job_post(db_session, title="Platform Engineer")
        third_job = await seed_test_job_post(db_session, title="Data Engineer")
        await seed_test_job_post_skills(
            db_session,
            job_post_id=first_job.id,
            skill_ids=[python.id, redis.id],
        )
        await seed_test_job_post_skills(
            db_session,
            job_post_id=second_job.id,
            skill_ids=[python.id, mysql.id],
        )
        await seed_test_job_post_skills(
            db_session,
            job_post_id=third_job.id,
            skill_ids=[python.id],
        )
        await pilot.workbench.create_target(
            user_id=user.id,
            payload=JobTargetCreate(job_post_id=first_job.id, is_primary=True),
        )
        await pilot.workbench.create_target(
            user_id=user.id,
            payload=JobTargetCreate(job_post_id=second_job.id),
        )
        await pilot.workbench.create_target(
            user_id=user.id,
            payload=JobTargetCreate(job_post_id=third_job.id),
        )
        await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(skill_id=python.id, proficiency_level=3),
        )

        response = await pilot.workbench.analyze_target_skill_summary(
            user_id=user.id,
        )

        assert response.target_count == 3
        assert response.primary_job_post_id == first_job.id
        assert response.other_target_count == 2
        assert [item.skill_name for item in response.items] == ["Python", "MySQL", "Redis"]
        assert [item.target_count for item in response.items] == [3, 1, 1]
        assert response.items[0].has_user_skill is True
        assert response.items[0].user_skill_status == JobMatchSkillStatus.MATCHED
        assert response.items[2].appears_in_primary_target is True
    finally:
        await truncate_workbench_tables(db_session)
