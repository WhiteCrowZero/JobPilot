from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from sqlalchemy import Select, and_, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from job_pilot.modules.job_posts.enums import JobPostStatus
from job_pilot.modules.job_posts.models import (
    JobPost,
    JobPostDetail,
    JobSource,
)
from job_pilot.modules.job_posts.schemas import JobPostSearchParams


@dataclass(slots=True)
class JobPostSearchResult:
    items: list[JobPost]
    total: int


class JobPostRepository:
    """岗位查询数据库操作。

    MVP 查询只依赖 job_posts 热字段和 detail.description 冷字段；
    地点不再 join 子表，locations 作为文本字段轻量筛选。
    标题搜索先用 ILIKE，后续接 ES/embedding 时可替换 keyword 查询入口。
    """

    async def search_job_posts(
        self,
        db: AsyncSession,
        params: JobPostSearchParams,
    ) -> JobPostSearchResult:
        base_stmt = self._build_base_search_stmt(params)

        count_stmt = self._build_count_stmt(base_stmt)
        total = await db.scalar(count_stmt) or 0

        page_stmt = (
            self._apply_sort(base_stmt, params)
            .offset(params.offset)
            .limit(params.page_size)
            .options(
                selectinload(JobPost.source),
                selectinload(JobPost.detail),
            )
        )
        result = await db.execute(page_stmt)
        items = list(result.scalars().unique().all())
        return JobPostSearchResult(items=items, total=total)

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

        stmt = (
            select(JobPost)
            .where(*conditions)
            .options(
                selectinload(JobPost.source),
                selectinload(JobPost.detail),
            )
        )
        return await db.scalar(stmt)

    def _build_base_search_stmt(self, params: JobPostSearchParams) -> Select[tuple[JobPost]]:
        stmt = select(JobPost).join(JobPost.source)
        conditions: list[ColumnElement[bool]] = [JobPost.deleted_at.is_(None)]

        if params.statuses:
            conditions.append(JobPost.status.in_(params.statuses))
        elif not params.include_closed:
            conditions.append(JobPost.status == JobPostStatus.OPEN)

        if params.source_platforms:
            conditions.append(JobSource.platform.in_(params.source_platforms))
        if params.employment_types:
            conditions.append(JobPost.employment_type.in_(params.employment_types))
        if params.workplace_types:
            conditions.append(JobPost.workplace_type.in_(params.workplace_types))
        if params.experience_levels:
            conditions.append(JobPost.experience_level.in_(params.experience_levels))
        if params.education_levels:
            conditions.append(JobPost.education_level.in_(params.education_levels))
        if params.is_remote is not None:
            conditions.append(JobPost.is_remote.is_(params.is_remote))

        # 经验区间：区间相交逻辑。未知经验不匹配经验筛选，避免误导。
        if params.experience_min_years is not None:
            conditions.append(JobPost.experience_max_years.is_not(None))
            conditions.append(JobPost.experience_max_years >= params.experience_min_years)
        if params.experience_max_years is not None:
            conditions.append(JobPost.experience_min_years.is_not(None))
            conditions.append(JobPost.experience_min_years <= params.experience_max_years)

        # 薪资区间：MVP 只比较已经解析出的数值，周期语义保留在 salary_text。
        if params.salary_currency is not None:
            conditions.append(JobPost.salary_currency == params.salary_currency)
        if params.salary_min is not None:
            conditions.append(JobPost.salary_max.is_not(None))
            conditions.append(JobPost.salary_max >= params.salary_min)
        if params.salary_max is not None:
            conditions.append(JobPost.salary_min.is_not(None))
            conditions.append(JobPost.salary_min <= params.salary_max)

        if params.published_from is not None:
            conditions.append(JobPost.published_at.is_not(None))
            conditions.append(JobPost.published_at >= params.published_from)
        if params.published_to is not None:
            conditions.append(JobPost.published_at.is_not(None))
            conditions.append(JobPost.published_at <= params.published_to)
        if params.seen_from is not None:
            conditions.append(JobPost.last_seen_at >= params.seen_from)
        if params.seen_to is not None:
            conditions.append(JobPost.last_seen_at <= params.seen_to)

        keyword = _clean_optional_text(params.keyword)
        if keyword is not None:
            keyword_like = f"%{keyword}%"
            detail_exists = cast(
                ColumnElement[bool],
                exists(
                    select(literal(1)).where(
                        JobPostDetail.job_post_id == JobPost.id,
                        JobPostDetail.description.ilike(keyword_like),
                    )
                ),
            )
            keyword_condition = or_(
                JobPost.title.ilike(keyword_like),
                JobPost.company_name.ilike(keyword_like),
                JobPost.locations.ilike(keyword_like),
                detail_exists,
            )
            conditions.append(keyword_condition)

        location_keywords = _clean_optional_list(params.locations)
        if location_keywords:
            conditions.append(
                or_(*(JobPost.locations.ilike(f"%{keyword}%") for keyword in location_keywords))
            )

        return stmt.where(and_(*conditions))

    def _apply_sort(
        self,
        stmt: Select[tuple[JobPost]],
        params: JobPostSearchParams,
    ) -> Select[tuple[JobPost]]:
        # 排序字段必须白名单控制，不允许前端直接传数据库字段名。
        match params.sort:
            case "published_at_asc":
                return stmt.order_by(JobPost.published_at.asc().nulls_last(), JobPost.id.asc())
            case "created_at_desc":
                return stmt.order_by(JobPost.created_at.desc(), JobPost.id.desc())
            case "created_at_asc":
                return stmt.order_by(JobPost.created_at.asc(), JobPost.id.asc())
            case "salary_max_desc":
                return stmt.order_by(JobPost.salary_max.desc().nulls_last(), JobPost.id.desc())
            case "salary_min_asc":
                return stmt.order_by(JobPost.salary_min.asc().nulls_last(), JobPost.id.asc())
            case _:
                return stmt.order_by(JobPost.published_at.desc().nulls_last(), JobPost.id.desc())

    def _build_count_stmt(self, base_stmt: Select[tuple[JobPost]]) -> Select[tuple[int]]:
        return select(func.count()).select_from(base_stmt.order_by(None).subquery())


class JobPostLookupRepository:
    """筛选项候选值查询。"""

    async def list_source_platforms(self, db: AsyncSession) -> list[str]:
        stmt = (
            select(JobSource.platform)
            .where(JobSource.is_active.is_(True))
            .distinct()
            .order_by(JobSource.platform)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_locations(self, db: AsyncSession) -> list[str]:
        stmt = (
            select(JobPost.locations)
            .where(JobPost.locations.is_not(None))
            .distinct()
            .order_by(JobPost.locations)
        )
        result = await db.execute(stmt)
        return [location for location in result.scalars().all() if location is not None]

    async def list_salary_currencies(self, db: AsyncSession) -> list[str]:
        stmt = (
            select(JobPost.salary_currency)
            .where(JobPost.salary_currency.is_not(None))
            .distinct()
            .order_by(JobPost.salary_currency)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned_value = value.strip()
    return cleaned_value or None


def _clean_optional_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned_values = [value.strip() for value in values if value.strip()]
    return list(dict.fromkeys(cleaned_values))
