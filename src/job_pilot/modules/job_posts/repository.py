from __future__ import annotations

from typing import cast

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from job_pilot.core.search import (
    SearchBackend,
    SortMap,
    apply_sort_by_key,
    clean_optional_int_list,
    clean_optional_list,
    clean_optional_text,
    fetch_page_ids,
    order_entities_by_ids,
)
from job_pilot.modules.job_posts.contracts import JobPostSearchQuery
from job_pilot.modules.job_posts.enums import JobPostStatus
from job_pilot.modules.job_posts.models import JobPost, JobSource
from job_pilot.modules.job_skills.models import JobPostSkill, Skill

JOB_POST_SORTS: SortMap = {
    "published_at_desc": lambda: cast(
        tuple[ColumnElement[object], ...],
        (JobPost.published_at.desc().nulls_last(), JobPost.id.desc()),
    ),
    "published_at_asc": lambda: cast(
        tuple[ColumnElement[object], ...],
        (JobPost.published_at.asc().nulls_last(), JobPost.id.asc()),
    ),
    "created_at_desc": lambda: cast(
        tuple[ColumnElement[object], ...],
        (JobPost.created_at.desc(), JobPost.id.desc()),
    ),
    "created_at_asc": lambda: cast(
        tuple[ColumnElement[object], ...],
        (JobPost.created_at.asc(), JobPost.id.asc()),
    ),
}


class JobPostRepository:
    """岗位查询数据库操作。

    MVP 查询只依赖 job_posts 岗位字段；
    地点不再 join 子表，locations 作为文本字段轻量筛选。
    文本搜索统一委托 SearchBackend，repository 不直接编码 LIKE 细节。
    """

    def __init__(self, search_backend: SearchBackend) -> None:
        self.search_backend = search_backend

    async def search_job_posts(
        self,
        db: AsyncSession,
        params: JobPostSearchQuery,
    ) -> list[JobPost]:
        base_stmt = self._build_base_search_stmt(params)
        sorted_stmt = self._apply_sort(base_stmt, params)
        job_post_ids = await fetch_page_ids(
            db,
            sorted_stmt,
            offset=params.offset,
            limit=params.limit,
        )
        if not job_post_ids:
            return []

        entity_stmt = (
            select(JobPost)
            .where(JobPost.id.in_(job_post_ids))
            .options(selectinload(JobPost.source))
        )
        entity_result = await db.execute(entity_stmt)
        return order_entities_by_ids(
            job_post_ids,
            entity_result.scalars().all(),
            get_id=lambda job_post: job_post.id,
        )

    async def get_job_post_detail(
        self,
        db: AsyncSession,
        job_post_id: int,
        *,
        include_deleted: bool = False,
    ) -> JobPost | None:
        conditions: list[ColumnElement[bool]] = [JobPost.id == job_post_id]
        if not include_deleted:
            conditions.append(JobPost.deleted_at.is_(None))

        stmt = select(JobPost).where(*conditions).options(selectinload(JobPost.source))
        return await db.scalar(stmt)

    def _build_base_search_stmt(self, params: JobPostSearchQuery) -> Select[tuple[int]]:
        stmt = select(JobPost.id).join(JobPost.source)
        conditions: list[ColumnElement[bool]] = [JobPost.deleted_at.is_(None)]

        if params.statuses is None:
            conditions.append(JobPost.status == JobPostStatus.OPEN)
        else:
            conditions.append(JobPost.status.in_(params.statuses))

        if params.source_platforms:
            conditions.append(JobSource.platform.in_(params.source_platforms))
        if params.education_levels:
            conditions.append(JobPost.education_level.in_(params.education_levels))

        if params.published_from is not None:
            conditions.append(JobPost.published_at.is_not(None))
            conditions.append(JobPost.published_at >= params.published_from)
        if params.published_to is not None:
            conditions.append(JobPost.published_at.is_not(None))
            conditions.append(JobPost.published_at <= params.published_to)

        keyword = clean_optional_text(params.keyword)
        if keyword is not None:
            keyword_condition = self.search_backend.contains_text_in_any_field(
                (
                    JobPost.title,
                    JobPost.locations,
                    JobPost.description,
                ),
                keyword,
            )
            conditions.append(keyword_condition)

        location_keywords = clean_optional_list(params.locations)
        if location_keywords:
            conditions.append(
                self.search_backend.contains_any_text(JobPost.locations, location_keywords)
            )

        skill_ids = clean_optional_int_list(params.skill_ids)
        if skill_ids:
            matched_job_ids = (
                select(JobPostSkill.job_post_id)
                .where(JobPostSkill.skill_id.in_(skill_ids))
                .group_by(JobPostSkill.job_post_id)
                .having(func.count(func.distinct(JobPostSkill.skill_id)) == len(skill_ids))
            )
            conditions.append(JobPost.id.in_(matched_job_ids))

        return stmt.where(and_(*conditions))

    def _apply_sort(
        self,
        stmt: Select[tuple[int]],
        params: JobPostSearchQuery,
    ) -> Select[tuple[int]]:
        # 排序字段必须白名单控制，不允许前端直接传数据库字段名。
        return apply_sort_by_key(
            stmt,
            sort_key=params.sort,
            sort_map=JOB_POST_SORTS,
            error_label="job post",
        )


class JobPostLookupRepository:
    """筛选项候选值查询。"""

    async def list_source_platforms(self, db: AsyncSession) -> list[str]:
        stmt = (
            select(JobSource.platform)
            .join(JobPost, JobPost.source_id == JobSource.id)
            .where(JobSource.is_active.is_(True))
            .where(*self._open_job_post_conditions())
            .distinct()
            .order_by(JobSource.platform)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_locations(self, db: AsyncSession) -> list[str]:
        stmt = (
            select(JobPost.locations)
            .where(*self._open_job_post_conditions(), JobPost.locations.is_not(None))
            .distinct()
            .order_by(JobPost.locations)
        )
        result = await db.execute(stmt)
        return [location for location in result.scalars().all() if location is not None]

    async def list_skills(self, db: AsyncSession) -> list[Skill]:
        """返回全部标准技能，供岗位筛选项使用。"""

        stmt = select(Skill).order_by(Skill.name.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _open_job_post_conditions(self) -> list[ColumnElement[bool]]:
        return [
            JobPost.deleted_at.is_(None),
            JobPost.status == JobPostStatus.OPEN,
        ]
