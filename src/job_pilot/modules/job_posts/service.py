from __future__ import annotations

import logging

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.cache import CacheStore
from job_pilot.core.pagination import trim_page_items
from job_pilot.core.search import SearchBackend
from job_pilot.modules.job_posts.contracts import JobPostSearchQuery
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    JobPostStatus,
)
from job_pilot.modules.job_posts.exceptions import JobPostNotFoundError
from job_pilot.modules.job_posts.models import JobPost
from job_pilot.modules.job_posts.repository import (
    JobPostLookupRepository,
    JobPostRepository,
)
from job_pilot.modules.job_posts.schemas import (
    JobPostDetailResponse,
    JobPostFilterOptionsResponse,
    JobPostListItem,
    JobPostListResponse,
)
from job_pilot.modules.job_skills.repository import JobPostSkillRepository
from job_pilot.modules.job_skills.schemas import SkillLabelResponse

FILTER_OPTIONS_CACHE_KEY = "job_posts:filter_options:open:v3"
FILTER_OPTIONS_CACHE_TTL_SECONDS = 60 * 30

logger = logging.getLogger(__name__)


class JobPostService:
    """岗位查询 service，负责查询编排和 ORM 到响应模型的转换。"""

    def __init__(
        self,
        repository: JobPostRepository,
        lookup_repository: JobPostLookupRepository,
        skill_repository: JobPostSkillRepository,
    ) -> None:
        self.repository = repository
        self.lookup_repository = lookup_repository
        self.skill_repository = skill_repository

    async def search_job_posts(
        self,
        db: AsyncSession,
        params: JobPostSearchQuery,
    ) -> JobPostListResponse:
        job_posts = await self.repository.search_job_posts(db=db, params=params)
        page_items, has_next = trim_page_items(
            job_posts,
            page_size=params.page_size,
        )
        return JobPostListResponse(
            items=[self._to_list_item(job_post) for job_post in page_items],
            page=params.page,
            page_size=params.page_size,
            total=None,
            has_next=has_next,
        )

    async def get_job_post_detail(
        self,
        db: AsyncSession,
        job_post_id: int,
    ) -> JobPostDetailResponse:
        job_post = await self.repository.get_job_post_detail(db=db, job_post_id=job_post_id)
        if job_post is None:
            raise JobPostNotFoundError()
        list_item = self._to_list_item(job_post)
        skill_labels = await self.skill_repository.list_skill_labels_for_job(
            db=db,
            job_post_id=job_post.id,
        )
        return JobPostDetailResponse(
            **list_item.model_dump(),
            skills=[SkillLabelResponse(id=skill_id, name=name) for skill_id, name in skill_labels],
            source_url=job_post.source_url,
            description=job_post.description,
        )

    async def get_filter_options(
        self,
        db: AsyncSession,
        cache: CacheStore,
    ) -> JobPostFilterOptionsResponse:
        cached_value = await cache.get(FILTER_OPTIONS_CACHE_KEY)
        if isinstance(cached_value, dict):
            try:
                return JobPostFilterOptionsResponse.model_validate(cached_value)
            except ValidationError:
                logger.error(
                    "Job post filter options cache payload was invalid",
                    extra={"cache_key": FILTER_OPTIONS_CACHE_KEY},
                )
                await cache.delete(FILTER_OPTIONS_CACHE_KEY)

        response = JobPostFilterOptionsResponse(
            source_platforms=await self.lookup_repository.list_source_platforms(db),
            statuses=list(JobPostStatus),
            education_levels=list(EducationLevel),
            locations=await self.lookup_repository.list_locations(db),
            skills=[
                SkillLabelResponse(id=skill.id, name=skill.name)
                for skill in await self.lookup_repository.list_skills(db)
            ],
        )
        await cache.set(
            FILTER_OPTIONS_CACHE_KEY,
            response.model_dump(mode="json"),
            ttl_seconds=FILTER_OPTIONS_CACHE_TTL_SECONDS,
        )
        return response

    @staticmethod
    def _to_list_item(job_post: JobPost) -> JobPostListItem:
        return JobPostListItem(
            id=job_post.id,
            source_platform=job_post.source.platform,
            source_name=job_post.source.name,
            source_base_url=job_post.source.base_url,
            title=job_post.title,
            locations=job_post.locations,
            experience_text=job_post.experience_text,
            education_level=job_post.education_level,
            salary_text=job_post.salary_text,
            published_at=job_post.published_at,
            created_at=job_post.created_at,
            status=job_post.status,
        )


def build_job_post_service(search_backend: SearchBackend) -> JobPostService:
    """组装岗位查询 service 的默认依赖。"""

    return JobPostService(
        repository=JobPostRepository(search_backend=search_backend),
        lookup_repository=JobPostLookupRepository(),
        skill_repository=JobPostSkillRepository(),
    )
