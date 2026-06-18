from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import NotFoundError
from job_pilot.core.pagination import trim_page_items
from job_pilot.core.search import SearchBackend
from job_pilot.modules.job_skills.contracts import (
    RawSkillCandidate,
    SkillAliasMatch,
    SkillNormalizationResult,
    SkillSyncResult,
)
from job_pilot.modules.job_skills.normalization import (
    build_skill_content_hash,
    normalize_skill_alias,
)
from job_pilot.modules.job_skills.repository import (
    JobPostSkillRepository,
    SkillDictionaryRepository,
)
from job_pilot.modules.job_skills.schemas import (
    SkillListItem,
    SkillListParams,
    SkillListResponse,
)


class SkillNormalizationService:
    """把 raw skill 文本归一到标准 skills。"""

    def __init__(self, repository: SkillDictionaryRepository) -> None:
        self.repository = repository

    async def normalize_candidates(
        self,
        db: AsyncSession,
        candidates: list[RawSkillCandidate],
    ) -> SkillNormalizationResult:
        alias_map = await self.repository.list_aliases(db)
        matched: list[SkillAliasMatch] = []
        unmatched: list[str] = []
        seen_skill_ids: set[int] = set()
        seen_unmatched_aliases: set[str] = set()

        for candidate in candidates:
            normalized_alias = normalize_skill_alias(candidate.text)
            if not normalized_alias:
                continue
            alias_match = alias_map.get(normalized_alias)
            if alias_match is None:
                if normalized_alias not in seen_unmatched_aliases:
                    unmatched.append(candidate.text)
                    seen_unmatched_aliases.add(normalized_alias)
                continue

            skill_id, skill_name = alias_match
            if skill_id in seen_skill_ids:
                continue
            matched.append(SkillAliasMatch(skill_id=skill_id, skill_name=skill_name))
            seen_skill_ids.add(skill_id)

        return SkillNormalizationResult(matched=matched, unmatched=unmatched)


class SkillDictionaryService:
    """技能数据字典 service。"""

    def __init__(self, repository: SkillDictionaryRepository) -> None:
        self.repository = repository

    async def list_skills(self, db: AsyncSession, params: SkillListParams) -> SkillListResponse:
        skills = await self.repository.list_skills(
            db=db,
            keyword=params.keyword,
            offset=params.offset,
            limit=params.limit + 1,
        )
        total = await self.repository.count_skills(db=db, keyword=params.keyword)
        page_items, has_next = trim_page_items(
            skills,
            page_size=params.page_size,
        )
        return SkillListResponse(
            items=[SkillListItem(id=skill.id, name=skill.name) for skill in page_items],
            page=params.page,
            page_size=params.page_size,
            total=total,
            has_next=has_next,
        )


class JobSkillSyncService:
    """岗位技能同步 service。"""

    def __init__(
        self,
        skill_normalization_service: SkillNormalizationService,
        repository: JobPostSkillRepository,
    ) -> None:
        self.skill_normalization_service = skill_normalization_service
        self.repository = repository

    async def sync_from_raw_candidates(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
        candidates: list[RawSkillCandidate],
    ) -> SkillSyncResult:
        """用当前 raw 技能候选替换岗位标准技能关系。

        本方法只负责事务 2 的业务内容：job_post_skills 与 job_posts.skill_content_hash。
        外层 orchestration/worker 决定何时调用和如何提交事务。
        """

        if not await self.repository.job_post_exists(db=db, job_post_id=job_post_id):
            raise NotFoundError("Job post not found", code="JOB_POST_NOT_FOUND")

        # 注意此处的业务设计就是空技能时，如果之前已有技能关系，旧标签不会清掉
        if not candidates:
            return SkillSyncResult(
                job_post_id=job_post_id,
                synced=False,
                skipped_reason="no_raw_skill_candidates",
                created_count=0,
                matched_count=0,
                unmatched_texts=[],
                skill_content_hash=None,
            )

        skill_content_hash = build_skill_content_hash(candidates)
        previous_hash = await self.repository.get_job_skill_content_hash(
            db=db,
            job_post_id=job_post_id,
        )
        if previous_hash == skill_content_hash:
            return SkillSyncResult(
                job_post_id=job_post_id,
                synced=False,
                skipped_reason="skill_content_hash_unchanged",
                created_count=0,
                matched_count=0,
                unmatched_texts=[],
                skill_content_hash=skill_content_hash,
            )

        normalization_result = await self.skill_normalization_service.normalize_candidates(
            db,
            candidates,
        )
        created_count = await self.repository.replace_skills_for_job(
            db=db,
            job_post_id=job_post_id,
            matches=normalization_result.matched,
        )
        await self.repository.update_job_skill_content_hash(
            db=db,
            job_post_id=job_post_id,
            skill_content_hash=skill_content_hash,
        )
        # TODO：filter-options 缓存后续改为后台刷新或在技能同步成功后统一失效。
        return SkillSyncResult(
            job_post_id=job_post_id,
            synced=True,
            skipped_reason=None,
            created_count=created_count,
            matched_count=len(normalization_result.matched),
            unmatched_texts=normalization_result.unmatched,
            skill_content_hash=skill_content_hash,
        )


def build_skill_dictionary_service(search_backend: SearchBackend) -> SkillDictionaryService:
    """组装技能字典 service。"""

    return SkillDictionaryService(repository=SkillDictionaryRepository(search_backend))


def build_skill_normalization_service(search_backend: SearchBackend) -> SkillNormalizationService:
    """组装技能归一化 service。"""

    return SkillNormalizationService(repository=SkillDictionaryRepository(search_backend))


def build_job_skill_sync_service(search_backend: SearchBackend) -> JobSkillSyncService:
    """组装岗位技能同步 service。"""

    return JobSkillSyncService(
        skill_normalization_service=build_skill_normalization_service(search_backend),
        repository=JobPostSkillRepository(),
    )
