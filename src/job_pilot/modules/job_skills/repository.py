from __future__ import annotations

from sqlalchemy import ColumnElement, delete, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import BadRequestError
from job_pilot.core.search import SearchBackend
from job_pilot.modules.job_posts.models import JobPost
from job_pilot.modules.job_skills.contracts import SkillAliasMatch
from job_pilot.modules.job_skills.models import JobPostSkill, Skill, SkillAlias


class SkillDictionaryRepository:
    """技能字典和别名表数据库操作。"""

    def __init__(self, search_backend: SearchBackend) -> None:
        self.search_backend = search_backend

    async def upsert_skill(
        self,
        *,
        db: AsyncSession,
        name: str,
    ) -> tuple[Skill, bool]:
        insert_stmt = pg_insert(Skill).values(
            name=name,
        )
        result = await db.execute(
            insert_stmt.on_conflict_do_update(
                constraint="uq_skills_name",
                set_={
                    "name": insert_stmt.excluded.name,
                },
            )
            .returning(Skill, literal_column("xmax = 0").label("created"))
            .execution_options(populate_existing=True)
        )
        skill, created = result.one()
        return skill, bool(created)

    async def upsert_alias(
        self,
        *,
        db: AsyncSession,
        skill_id: int,
        alias: str,
    ) -> bool:
        from job_pilot.modules.job_skills.normalization import normalize_skill_alias

        normalized_alias = normalize_skill_alias(alias)
        if not normalized_alias:
            raise BadRequestError("Skill alias must not be empty", code="SKILL_ALIAS_EMPTY")

        result = await db.execute(
            pg_insert(SkillAlias)
            .values(
                skill_id=skill_id,
                alias=normalized_alias,
            )
            .on_conflict_do_update(
                constraint="uq_skill_aliases_alias",
                set_={
                    "skill_id": skill_id,
                },
            )
            .returning(literal_column("xmax = 0").label("created"))
        )
        return bool(result.scalar_one())

    async def list_aliases(self, db: AsyncSession) -> dict[str, tuple[int, str]]:
        """返回 alias -> (skill_id, skill_name)。"""

        stmt = select(SkillAlias.alias, Skill.id, Skill.name).join(
            Skill, Skill.id == SkillAlias.skill_id
        )
        result = await db.execute(stmt)
        return {alias: (skill_id, skill_name) for alias, skill_id, skill_name in result.all()}

    async def list_skills(
        self,
        *,
        db: AsyncSession,
        keyword: str | None,
        offset: int,
        limit: int,
    ) -> list[Skill]:
        conditions = self._build_skill_conditions(keyword)
        stmt = (
            select(Skill).where(*conditions).order_by(Skill.name.asc()).offset(offset).limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_skills(
        self,
        *,
        db: AsyncSession,
        keyword: str | None,
    ) -> int:
        conditions = self._build_skill_conditions(keyword)
        stmt = select(func.count(Skill.id)).where(*conditions)
        result = await db.execute(stmt)
        return result.scalar_one()

    def _build_skill_conditions(self, keyword: str | None) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        cleaned_keyword = keyword.strip() if keyword is not None else None
        if cleaned_keyword:
            conditions.append(self.search_backend.contains_text(Skill.name, cleaned_keyword))
        return conditions


class JobPostSkillRepository:
    """岗位技能关系数据库操作。"""

    async def job_post_exists(self, *, db: AsyncSession, job_post_id: int) -> bool:
        """判断岗位是否存在且未软删除。"""

        result = await db.execute(
            select(JobPost.id)
            .where(
                JobPost.id == job_post_id,
                JobPost.deleted_at.is_(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_job_skill_content_hash(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
    ) -> str | None:
        """读取岗位当前已同步技能内容 hash。"""

        result = await db.execute(
            select(JobPost.skill_content_hash).where(JobPost.id == job_post_id)
        )
        return result.scalar_one_or_none()

    async def update_job_skill_content_hash(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
        skill_content_hash: str | None,
    ) -> None:
        """更新岗位当前已同步技能内容 hash。"""

        job_post = await db.get(JobPost, job_post_id)
        if job_post is None:
            return
        job_post.skill_content_hash = skill_content_hash
        await db.flush()

    async def replace_skills_for_job(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
        matches: list[SkillAliasMatch],
    ) -> int:
        """替换某个岗位的标准技能关系。"""

        await db.execute(delete(JobPostSkill).where(JobPostSkill.job_post_id == job_post_id))

        created_count = 0
        for match in matches:
            result = await db.execute(
                pg_insert(JobPostSkill)
                .values(
                    job_post_id=job_post_id,
                    skill_id=match.skill_id,
                )
                .on_conflict_do_nothing(constraint="uq_job_post_skills_job_skill")
                .returning(JobPostSkill.id)
            )
            if result.scalar_one_or_none() is not None:
                created_count += 1
        await db.flush()
        return created_count

    async def list_skill_labels_for_job(
        self,
        *,
        db: AsyncSession,
        job_post_id: int,
    ) -> list[tuple[int, str]]:
        stmt = (
            select(Skill.id, Skill.name)
            .join(JobPostSkill, JobPostSkill.skill_id == Skill.id)
            .where(JobPostSkill.job_post_id == job_post_id)
            .order_by(Skill.name.asc())
        )
        result = await db.execute(stmt)
        return [(skill_id, skill_name) for skill_id, skill_name in result.all()]
