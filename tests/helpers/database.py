from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def truncate_auth_user_tables(session: AsyncSession) -> None:
    """清理认证和用户主体相关测试数据。"""

    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                auth_password_credentials,
                auth_identities,
                user_profiles,
                users
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()


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


async def truncate_job_tables(session: AsyncSession) -> None:
    """清理岗位、摄入和技能字典相关测试数据。"""

    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
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


async def truncate_knowledge_tables(session: AsyncSession) -> None:
    """清理知识点树和技能字典相关测试数据。"""

    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                knowledge_points,
                skill_aliases,
                skills
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()


async def truncate_learning_tables(session: AsyncSession) -> None:
    """清理学习闭环、题库、岗位目标和用户主体测试数据。"""

    await session.rollback()
    await session.execute(
        text(
            """
            TRUNCATE TABLE
                study_task_question_attempts,
                study_task_questions,
                study_task_progress,
                study_task_snapshots,
                study_tasks,
                question_options,
                question_answers,
                question_skills,
                questions,
                knowledge_points,
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
                skills,
                auth_password_credentials,
                auth_identities,
                user_profiles,
                users
            RESTART IDENTITY CASCADE
            """
        )
    )
    await session.commit()
