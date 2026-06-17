from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.application import JobPilot
from job_pilot.modules.job_skills.models import SkillAlias
from job_pilot.modules.job_skills.repository import SkillDictionaryRepository
from job_pilot.modules.job_skills.schemas import SkillListParams
from tests.helpers.database import truncate_job_tables


@pytest.mark.asyncio
async def test_repository_stores_multiple_aliases_for_one_skill(
    db_session: AsyncSession,
) -> None:
    """技能字典仓储会按规范化别名去重。"""

    await truncate_job_tables(db_session)
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
        await truncate_job_tables(db_session)


@pytest.mark.asyncio
async def test_list_skills_total_respects_keyword_filter(
    pilot: JobPilot,
    db_session: AsyncSession,
) -> None:
    """公开技能入口返回符合关键词筛选的总数。"""

    await truncate_job_tables(db_session)
    repository = SkillDictionaryRepository()

    try:
        await repository.upsert_skill(db=db_session, name="Python")
        await repository.upsert_skill(db=db_session, name="FastAPI")
        await repository.upsert_skill(db=db_session, name="Redis")
        await db_session.commit()

        result = await pilot.skills.list_skills(SkillListParams(keyword="py", page=1, page_size=10))

        assert result.total == 1
        assert [item.name for item in result.items] == ["Python"]
        assert result.has_next is False
    finally:
        await truncate_job_tables(db_session)
