from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.job_collections.models import JobCollection, JobCollectionFolder
from job_pilot.modules.job_posts.models import JobPost, JobSource
from job_pilot.modules.job_skills.models import Skill
from job_pilot.modules.job_skills.repository import SkillDictionaryRepository
from job_pilot.modules.job_targets.models import JobTarget
from job_pilot.modules.users import repository as user_repository
from job_pilot.modules.users.models import User


async def create_test_user(
    session: AsyncSession,
    *,
    display_name: str = "Test User",
) -> User:
    """创建测试用户并提交事务。"""

    user = await user_repository.create_user(display_name=display_name, session=session)
    await session.commit()
    return user


async def seed_test_skill(session: AsyncSession, name: str) -> Skill:
    """创建或更新一个标准技能。"""

    repository = SkillDictionaryRepository()
    skill, _ = await repository.upsert_skill(db=session, name=name)
    await session.commit()
    return skill


async def seed_test_skills(session: AsyncSession, names: Iterable[str]) -> list[Skill]:
    """批量创建标准技能。"""

    skills: list[Skill] = []
    repository = SkillDictionaryRepository()
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
        company_name="Test Company",
        locations="Remote",
        is_remote=True,
    )
    session.add(job_post)
    await session.commit()
    return job_post


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


async def truncate_user_skill_tables(session: AsyncSession) -> None:
    """清理用户技能画像相关测试数据。"""

    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                user_skills,
                job_post_skills,
                skill_aliases,
                skills
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()


async def truncate_workbench_tables(session: AsyncSession) -> None:
    """清理用户工作台相关测试数据。"""

    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                user_skills,
                job_targets,
                job_collections,
                job_collection_folders,
                job_post_skills,
                job_post_details,
                job_posts,
                raw_job_records,
                job_sources,
                skill_aliases,
                skills
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()
