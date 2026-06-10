from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.ingestion.normalization.skills import (
    build_skill_content_hash,
    extract_raw_skill_candidates,
    normalize_skill_alias,
)
from job_pilot.modules.job_skills.models import SkillAlias
from job_pilot.modules.job_skills.repository import (
    JobPostSkillRepository,
    SkillDictionaryRepository,
)
from job_pilot.modules.job_skills.schemas import SkillListParams
from job_pilot.modules.job_skills.service import (
    JobSkillSyncService,
    SkillDictionaryService,
    SkillNormalizationService,
)
from job_pilot.modules.job_skills.skill_sync_contracts import RawSkillCandidate, SkillAliasMatch


class FakeSkillDictionaryRepository(SkillDictionaryRepository):
    async def list_aliases(self, db: AsyncSession) -> dict[str, tuple[int, str]]:
        _ = db
        return {
            "python": (1, "Python"),
            "py": (1, "Python"),
            "fastapi": (2, "FastAPI"),
            "postgres": (3, "PostgreSQL"),
            "postgresql": (3, "PostgreSQL"),
            "redis": (4, "Redis"),
        }


class FakeJobPostSkillRepository(JobPostSkillRepository):
    def __init__(self, previous_hash: str | None = None) -> None:
        self.previous_hash = previous_hash
        self.updated_hash: str | None = None
        self.replaced_matches: list[SkillAliasMatch] = []

    async def get_job_skill_content_hash(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
    ) -> str | None:
        _ = db, job_post_id
        return self.previous_hash

    async def update_job_skill_content_hash(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
        skill_content_hash: str | None,
    ) -> None:
        _ = db, job_post_id
        self.updated_hash = skill_content_hash

    async def replace_skills_for_job(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
        matches: list[SkillAliasMatch],
    ) -> int:
        _ = db, job_post_id
        self.replaced_matches = matches
        return len(matches)


def test_normalize_skill_alias_handles_case_space_and_symbols() -> None:
    assert normalize_skill_alias(" Fast API ") == "fastapi"
    assert normalize_skill_alias("PostgreSQL") == "postgresql"
    assert normalize_skill_alias("C++") == "c++"
    assert normalize_skill_alias("C#") == "c#"


def test_extract_raw_skill_candidates_only_reads_structured_fields() -> None:
    candidates = extract_raw_skill_candidates(["Python", "Fast API", "Redis, Docker"])

    assert [candidate.text for candidate in candidates] == ["Python", "Fast API", "Redis", "Docker"]


def test_build_skill_content_hash_is_stable_after_reordering() -> None:
    candidates_a = [RawSkillCandidate("Python"), RawSkillCandidate("Fast API")]
    candidates_b = [RawSkillCandidate("fastapi"), RawSkillCandidate("python")]

    assert build_skill_content_hash(candidates_a) == build_skill_content_hash(candidates_b)


@pytest.mark.asyncio
async def test_normalize_candidates_maps_alias_to_standard_skill() -> None:
    service = SkillNormalizationService(repository=FakeSkillDictionaryRepository())

    result = await service.normalize_candidates(
        cast(AsyncSession, object()),
        [
            RawSkillCandidate("Python"),
            RawSkillCandidate("py"),
            RawSkillCandidate("Fast API"),
            RawSkillCandidate("UnknownSkill"),
        ],
    )

    assert [(match.skill_id, match.skill_name) for match in result.matched] == [
        (1, "Python"),
        (2, "FastAPI"),
    ]
    assert result.unmatched == ["UnknownSkill"]


@pytest.mark.asyncio
async def test_repository_stores_multiple_aliases_for_one_skill(
    db_session: AsyncSession,
) -> None:
    await truncate_skill_tables(db_session)
    repository = SkillDictionaryRepository()

    try:
        skill, _ = await repository.upsert_skill(db=db_session, name="PostgreSQL")
        await repository.upsert_alias(db=db_session, skill_id=skill.id, alias="PostgreSQL")
        await repository.upsert_alias(db=db_session, skill_id=skill.id, alias="Postgres")
        await repository.upsert_alias(db=db_session, skill_id=skill.id, alias="pg")
        await repository.upsert_alias(db=db_session, skill_id=skill.id, alias="P G")
        await db_session.commit()

        alias_map = await repository.list_aliases(db_session)
        stored_aliases = (
            (await db_session.execute(select(SkillAlias.alias).order_by(SkillAlias.alias.asc())))
            .scalars()
            .all()
        )

        assert stored_aliases == ["pg", "postgres", "postgresql"]
        assert alias_map["postgresql"] == (skill.id, "PostgreSQL")
        assert alias_map["postgres"] == (skill.id, "PostgreSQL")
        assert alias_map["pg"] == (skill.id, "PostgreSQL")
    finally:
        await truncate_skill_tables(db_session)


@pytest.mark.asyncio
async def test_list_skills_total_respects_keyword_filter(db_session: AsyncSession) -> None:
    await truncate_skill_tables(db_session)
    repository = SkillDictionaryRepository()
    service = SkillDictionaryService(repository=repository)

    try:
        await repository.upsert_skill(db=db_session, name="Python")
        await repository.upsert_skill(db=db_session, name="FastAPI")
        await repository.upsert_skill(db=db_session, name="Redis")
        await db_session.commit()

        result = await service.list_skills(
            db_session,
            params=SkillListParams(keyword="py", page=1, page_size=10),
        )

        assert result.total == 1
        assert [item.name for item in result.items] == ["Python"]
        assert result.has_next is False
    finally:
        await truncate_skill_tables(db_session)


@pytest.mark.asyncio
async def test_sync_from_raw_candidates_replaces_job_skills() -> None:
    candidates = [RawSkillCandidate("Python"), RawSkillCandidate("Postgres")]
    fake_repository = FakeJobPostSkillRepository()
    service = JobSkillSyncService(
        skill_normalization_service=SkillNormalizationService(
            repository=FakeSkillDictionaryRepository()
        ),
        repository=fake_repository,
    )

    result = await service.sync_from_raw_candidates(
        db=cast(AsyncSession, object()),
        job_post_id=1,
        candidates=candidates,
    )

    assert result.synced is True
    assert result.created_count == 2
    assert [(match.skill_id, match.skill_name) for match in fake_repository.replaced_matches] == [
        (1, "Python"),
        (3, "PostgreSQL"),
    ]
    assert fake_repository.updated_hash == build_skill_content_hash(candidates)


@pytest.mark.asyncio
async def test_sync_from_raw_candidates_skips_when_hash_unchanged() -> None:
    candidates = [RawSkillCandidate("Python"), RawSkillCandidate("Postgres")]
    skill_content_hash = build_skill_content_hash(candidates)
    fake_repository = FakeJobPostSkillRepository(previous_hash=skill_content_hash)
    service = JobSkillSyncService(
        skill_normalization_service=SkillNormalizationService(
            repository=FakeSkillDictionaryRepository()
        ),
        repository=fake_repository,
    )

    result = await service.sync_from_raw_candidates(
        db=cast(AsyncSession, object()),
        job_post_id=1,
        candidates=candidates,
    )

    assert result.synced is False
    assert result.skipped_reason == "skill_content_hash_unchanged"
    assert fake_repository.replaced_matches == []


@pytest.mark.asyncio
async def test_sync_from_raw_candidates_clears_skills_when_candidates_become_empty() -> None:
    fake_repository = FakeJobPostSkillRepository(previous_hash="old-hash")
    service = JobSkillSyncService(
        skill_normalization_service=SkillNormalizationService(
            repository=FakeSkillDictionaryRepository()
        ),
        repository=fake_repository,
    )

    result = await service.sync_from_raw_candidates(
        db=cast(AsyncSession, object()),
        job_post_id=1,
        candidates=[],
    )

    assert result.synced is False
    assert result.created_count == 0
    assert fake_repository.replaced_matches == []
    assert result.skipped_reason == "no_raw_skill_candidates"
    assert fake_repository.updated_hash is None


async def truncate_skill_tables(session: AsyncSession) -> None:
    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                job_post_skills,
                skill_aliases,
                skills
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()
