from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.search import SqlLikeSearchBackend
from job_pilot.modules.job_collections.models import JobCollection, JobCollectionFolder
from job_pilot.modules.job_posts.models import JobPost, JobSource
from job_pilot.modules.job_skills.models import JobPostSkill, Skill
from job_pilot.modules.job_skills.repository import SkillDictionaryRepository
from job_pilot.modules.job_targets.models import JobTarget
from job_pilot.modules.users.models import User
from job_pilot.modules.users.service import build_user_service

user_service = build_user_service()


async def create_test_user(
    session: AsyncSession,
    *,
    display_name: str = "Test User",
) -> User:
    """创建测试用户并提交事务。"""

    user = await user_service.create_user(session, display_name=display_name)
    await session.commit()
    return user


async def seed_test_skill(session: AsyncSession, name: str) -> Skill:
    """创建或更新一个标准技能。"""

    repository = SkillDictionaryRepository(SqlLikeSearchBackend())
    skill, _ = await repository.upsert_skill(db=session, name=name)
    await session.commit()
    return skill


async def seed_test_skills(session: AsyncSession, names: Iterable[str]) -> list[Skill]:
    """批量创建标准技能。"""

    skills: list[Skill] = []
    repository = SkillDictionaryRepository(SqlLikeSearchBackend())
    for name in names:
        skill, _ = await repository.upsert_skill(db=session, name=name)
        skills.append(skill)
    await session.commit()
    return skills


async def seed_test_job_source(
    session: AsyncSession,
    *,
    platform: str = "test",
    name: str = "Test Jobs",
    base_url: str | None = None,
) -> JobSource:
    """创建测试岗位来源。"""

    source = JobSource(
        platform=platform,
        name=name,
        base_url=base_url or f"https://jobs.example.com/{uuid4().hex}",
    )
    session.add(source)
    await session.commit()
    return source


async def seed_test_job_post(
    session: AsyncSession,
    *,
    title: str = "Backend Engineer",
    source: JobSource | None = None,
) -> JobPost:
    """创建最小可用测试岗位。"""

    job_source = source
    if job_source is None:
        job_source = await seed_test_job_source(session)
    job_post = JobPost(
        source_id=job_source.id,
        fingerprint=f"test-{uuid4().hex}",
        title=title,
        locations="Remote",
    )
    session.add(job_post)
    await session.commit()
    return job_post


async def seed_test_job_post_skill(
    session: AsyncSession,
    *,
    job_post_id: int,
    skill_id: int,
) -> JobPostSkill:
    """创建测试岗位技能关系。"""

    job_post_skill = JobPostSkill(job_post_id=job_post_id, skill_id=skill_id)
    session.add(job_post_skill)
    await session.commit()
    return job_post_skill


async def seed_test_job_post_skills(
    session: AsyncSession,
    *,
    job_post_id: int,
    skill_ids: Iterable[int],
) -> list[JobPostSkill]:
    """批量创建测试岗位技能关系。"""

    links: list[JobPostSkill] = []
    for skill_id in skill_ids:
        links.append(JobPostSkill(job_post_id=job_post_id, skill_id=skill_id))
    session.add_all(links)
    await session.commit()
    return links


async def seed_test_collection_folder(
    session: AsyncSession,
    *,
    user_id: int,
    name: str = "Default Folder",
) -> JobCollectionFolder:
    """创建测试收藏夹。"""

    folder = JobCollectionFolder(user_id=user_id, name=name)
    session.add(folder)
    await session.commit()
    return folder


async def seed_test_collection(
    session: AsyncSession,
    *,
    user_id: int,
    job_post_id: int,
    folder_id: int | None = None,
) -> JobCollection:
    """创建测试岗位收藏。"""

    collection = JobCollection(
        user_id=user_id,
        job_post_id=job_post_id,
        folder_id=folder_id,
    )
    session.add(collection)
    await session.commit()
    return collection


async def seed_test_target(
    session: AsyncSession,
    *,
    user_id: int,
    job_post_id: int,
    is_primary: bool = False,
) -> JobTarget:
    """创建测试目标岗位。"""

    target = JobTarget(
        user_id=user_id,
        job_post_id=job_post_id,
        is_primary=is_primary,
    )
    session.add(target)
    await session.commit()
    return target
