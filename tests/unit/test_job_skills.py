from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import NotFoundError
from job_pilot.modules.job_skills.normalization import (
    build_skill_content_hash,
    extract_raw_skill_candidates,
    normalize_skill_alias,
)
from job_pilot.modules.job_skills.repository import (
    JobPostSkillRepository,
    SkillDictionaryRepository,
)
from job_pilot.modules.job_skills.service import (
    JobSkillSyncService,
    SkillNormalizationService,
)
from job_pilot.modules.job_skills.skill_sync_contracts import RawSkillCandidate, SkillAliasMatch


class FakeSkillDictionaryRepository(SkillDictionaryRepository):
    def __init__(self) -> None:
        pass

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
    def __init__(self, previous_hash: str | None = None, job_post_exists: bool = True) -> None:
        self.previous_hash = previous_hash
        self._job_post_exists = job_post_exists
        self.updated_hash: str | None = None
        self.replaced_matches: list[SkillAliasMatch] = []

    async def job_post_exists(self, *, db: AsyncSession, job_post_id: int) -> bool:
        _ = db, job_post_id
        return self._job_post_exists

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
async def test_sync_from_raw_candidates_keeps_existing_skills_when_candidates_are_absent() -> None:
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


@pytest.mark.asyncio
async def test_sync_from_raw_candidates_rejects_missing_job_post() -> None:
    service = JobSkillSyncService(
        skill_normalization_service=SkillNormalizationService(
            repository=FakeSkillDictionaryRepository()
        ),
        repository=FakeJobPostSkillRepository(job_post_exists=False),
    )

    with pytest.raises(NotFoundError) as exc_info:
        await service.sync_from_raw_candidates(
            db=cast(AsyncSession, object()),
            job_post_id=999_999,
            candidates=[RawSkillCandidate("Python")],
        )

    assert exc_info.value.code == "JOB_POST_NOT_FOUND"
