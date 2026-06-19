from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.user_skills.contracts import (
    UserSkillListQuery as UserSkillListParams,
)
from job_pilot.modules.user_skills.contracts import (
    UserSkillUpdateCommand as UserSkillUpdate,
)
from job_pilot.modules.user_skills.contracts import (
    UserSkillUpsertCommand as UserSkillUpsert,
)
from job_pilot.modules.user_skills.enums import UserSkillSource, UserSkillStatus
from job_pilot.modules.user_skills.exceptions import (
    StandardSkillNotFoundError,
    UserSkillNotFoundError,
)
from tests.helpers.builders import (
    create_test_user,
    seed_test_skill,
    seed_test_skills,
)
from tests.helpers.database import truncate_user_skill_tables


@pytest.mark.asyncio
async def test_restore_archived_skill_preserves_unset_profile_fields(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")

        created = await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(
                skill_id=skill.id,
                source=UserSkillSource.ASSESSMENT,
                proficiency_level=4,
                interest_level=5,
                years_of_experience=Decimal("2.5"),
                last_used_at=date(2026, 6, 1),
                evidence="Used in backend services",
                note="Keep this profile",
            ),
        )
        archived = await pilot.workbench.archive_user_skill(
            user_id=user.id,
            skill_id=skill.id,
        )
        restored = await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(skill_id=skill.id),
        )

        assert archived.status == UserSkillStatus.ARCHIVED
        assert archived.archived_at is not None
        assert restored.id == created.id
        assert restored.status == UserSkillStatus.ACTIVE
        assert restored.archived_at is None
        assert restored.source == UserSkillSource.ASSESSMENT
        assert restored.proficiency_level == 4
        assert restored.interest_level == 5
        assert restored.years_of_experience == Decimal("2.5")
        assert restored.last_used_at == date(2026, 6, 1)
        assert restored.evidence == "Used in backend services"
        assert restored.note == "Keep this profile"
    finally:
        await truncate_user_skill_tables(db_session)


@pytest.mark.asyncio
async def test_restore_archived_skill_overwrites_explicit_fields(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "FastAPI")

        created = await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(
                skill_id=skill.id,
                source=UserSkillSource.SELF_REPORTED,
                proficiency_level=2,
                interest_level=3,
                years_of_experience=Decimal("1.0"),
                last_used_at=date(2025, 12, 1),
                evidence="Old evidence",
                note="Old note",
            ),
        )
        await pilot.workbench.archive_user_skill(
            user_id=user.id,
            skill_id=skill.id,
        )
        restored = await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(
                skill_id=skill.id,
                source=UserSkillSource.ASSESSMENT,
                proficiency_level=5,
                interest_level=1,
                years_of_experience=Decimal("3.0"),
                last_used_at=date(2026, 6, 1),
                evidence=None,
                note="New note",
                fields_set=frozenset(
                    {
                        "skill_id",
                        "source",
                        "proficiency_level",
                        "interest_level",
                        "years_of_experience",
                        "last_used_at",
                        "evidence",
                        "note",
                    }
                ),
            ),
        )

        assert restored.id == created.id
        assert restored.status == UserSkillStatus.ACTIVE
        assert restored.archived_at is None
        assert restored.source == UserSkillSource.ASSESSMENT
        assert restored.proficiency_level == 5
        assert restored.interest_level == 1
        assert restored.years_of_experience == Decimal("3.0")
        assert restored.last_used_at == date(2026, 6, 1)
        assert restored.evidence is None
        assert restored.note == "New note"
    finally:
        await truncate_user_skill_tables(db_session)


@pytest.mark.asyncio
async def test_upsert_user_skill_creates_and_restores_archived_profile(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "Python")

        created = await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(
                skill_id=skill.id,
                proficiency_level=2,
                interest_level=4,
                years_of_experience=Decimal("1.5"),
                evidence="Original evidence",
                note="Original note",
            ),
        )
        archived = await pilot.workbench.archive_user_skill(
            user_id=user.id,
            skill_id=skill.id,
        )
        restored = await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(
                skill_id=skill.id,
                source=UserSkillSource.ASSESSMENT,
                proficiency_level=5,
                interest_level=3,
            ),
        )

        assert created.status == UserSkillStatus.ACTIVE
        assert archived.status == UserSkillStatus.ARCHIVED
        assert archived.archived_at is not None
        assert restored.id == created.id
        assert restored.status == UserSkillStatus.ACTIVE
        assert restored.archived_at is None
        assert restored.source == UserSkillSource.ASSESSMENT
        assert restored.proficiency_level == 5
        assert restored.years_of_experience == Decimal("1.5")
        assert restored.evidence == "Original evidence"
        assert restored.note == "Original note"
    finally:
        await truncate_user_skill_tables(db_session)


@pytest.mark.asyncio
async def test_upsert_user_skill_rejects_missing_standard_skill(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        user = await create_test_user(db_session)

        with pytest.raises(StandardSkillNotFoundError):
            await pilot.workbench.upsert_user_skill(
                user_id=user.id,
                payload=UserSkillUpsert(skill_id=999_999),
            )
    finally:
        await truncate_user_skill_tables(db_session)


@pytest.mark.asyncio
async def test_update_user_skill_and_list_with_skill_filter(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        user = await create_test_user(db_session)
        python, redis = await seed_test_skills(db_session, ["Python", "Redis"])
        await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(skill_id=python.id, proficiency_level=2, interest_level=5),
        )
        await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(skill_id=redis.id, proficiency_level=4, interest_level=3),
        )

        updated = await pilot.workbench.update_user_skill(
            user_id=user.id,
            skill_id=python.id,
            payload=UserSkillUpdate(
                proficiency_level=5,
                evidence="Used in JobPilot backend",
                note=None,
            ),
        )
        filtered = await pilot.workbench.list_user_skills(
            user_id=user.id,
            params=UserSkillListParams(skill_ids=[python.id], page=1, page_size=10),
        )
        all_profiles = await pilot.workbench.list_user_skills(
            user_id=user.id,
            params=UserSkillListParams(page=1, page_size=10),
        )

        assert updated.proficiency_level == 5
        assert updated.evidence == "Used in JobPilot backend"
        assert updated.note is None
        assert [item.skill_id for item in filtered.items] == [python.id]
        assert [item.skill_id for item in all_profiles.items] == [python.id, redis.id]
    finally:
        await truncate_user_skill_tables(db_session)


@pytest.mark.asyncio
async def test_archive_user_skill_excludes_profile_from_default_list(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        user = await create_test_user(db_session)
        skill = await seed_test_skill(db_session, "FastAPI")
        await pilot.workbench.upsert_user_skill(
            user_id=user.id,
            payload=UserSkillUpsert(skill_id=skill.id),
        )

        archived = await pilot.workbench.archive_user_skill(
            user_id=user.id,
            skill_id=skill.id,
        )
        active_list = await pilot.workbench.list_user_skills(
            user_id=user.id,
            params=UserSkillListParams(page=1, page_size=10),
        )
        archived_list = await pilot.workbench.list_user_skills(
            user_id=user.id,
            params=UserSkillListParams(
                statuses=[UserSkillStatus.ARCHIVED],
                page=1,
                page_size=10,
            ),
        )

        assert archived.status == UserSkillStatus.ARCHIVED
        assert active_list.items == []
        assert [item.skill_id for item in archived_list.items] == [skill.id]
    finally:
        await truncate_user_skill_tables(db_session)


@pytest.mark.asyncio
async def test_update_user_skill_hides_other_users_profile(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    await truncate_user_skill_tables(db_session)

    try:
        owner = await create_test_user(db_session, display_name="Owner")
        other_user = await create_test_user(db_session, display_name="Other")
        skill = await seed_test_skill(db_session, "PostgreSQL")
        await pilot.workbench.upsert_user_skill(
            user_id=owner.id,
            payload=UserSkillUpsert(skill_id=skill.id),
        )

        with pytest.raises(UserSkillNotFoundError):
            await pilot.workbench.update_user_skill(
                user_id=other_user.id,
                skill_id=skill.id,
                payload=UserSkillUpdate(proficiency_level=3),
            )
    finally:
        await truncate_user_skill_tables(db_session)
