from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.job_skills.contracts import RawSkillCandidate, SkillAliasMatch
from job_pilot.modules.job_skills.exceptions import JobPostForSkillSyncNotFoundError
from job_pilot.modules.job_skills.normalization import (
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
    def __init__(self, job_post_exists: bool = True) -> None:
        self._job_post_exists = job_post_exists
        self.replaced_matches: list[SkillAliasMatch] = []

    async def job_post_exists(self, *, db: AsyncSession, job_post_id: int) -> bool:
        _ = db, job_post_id
        return self._job_post_exists

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


@pytest.mark.asyncio
async def test_sync_from_raw_candidates_keeps_existing_skills_when_candidates_are_absent() -> None:
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
        candidates=[],
    )

    assert result.synced is False
    assert result.created_count == 0
    assert fake_repository.replaced_matches == []
    assert result.skipped_reason == "no_raw_skill_candidates"


@pytest.mark.asyncio
async def test_sync_from_raw_candidates_rejects_missing_job_post() -> None:
    service = JobSkillSyncService(
        skill_normalization_service=SkillNormalizationService(
            repository=FakeSkillDictionaryRepository()
        ),
        repository=FakeJobPostSkillRepository(job_post_exists=False),
    )

    with pytest.raises(JobPostForSkillSyncNotFoundError) as exc_info:
        await service.sync_from_raw_candidates(
            db=cast(AsyncSession, object()),
            job_post_id=999_999,
            candidates=[RawSkillCandidate("Python")],
        )

    assert exc_info.value.code == "JOB_POST_NOT_FOUND"
