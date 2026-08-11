from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from job_pilot.core.config import settings
from job_pilot.core.resources import build_database_only_resources
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.job_posts.models import JobPost, JobSource
from job_pilot.modules.job_skills.models import JobPostSkill, Skill


async def main() -> None:
    """核查 simulator 固定岗位经过 MQ 后的数据库结果。"""

    resources = build_database_only_resources(settings)
    try:
        async with resources.require_database().session_factory() as session:
            raw_records = (
                (
                    await session.execute(
                        select(RawJobRecord)
                        .join(JobSource, JobSource.id == RawJobRecord.source_id)
                        .where(
                            JobSource.platform == "mock",
                            RawJobRecord.external_job_id == "mock-10001",
                        )
                        .order_by(RawJobRecord.id)
                    )
                )
                .scalars()
                .all()
            )
            job_post = (
                await session.execute(
                    select(JobPost)
                    .join(JobSource, JobSource.id == JobPost.source_id)
                    .where(
                        JobSource.platform == "mock",
                        JobPost.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            skill_names = []
            if job_post is not None:
                skill_names = list(
                    (
                        await session.execute(
                            select(Skill.name)
                            .join(JobPostSkill, JobPostSkill.skill_id == Skill.id)
                            .where(JobPostSkill.job_post_id == job_post.id)
                            .order_by(Skill.name)
                        )
                    ).scalars()
                )
            job_count = await session.scalar(
                select(func.count(JobPost.id))
                .join(JobSource, JobSource.id == JobPost.source_id)
                .where(JobSource.platform == "mock")
            )

        print(f"raw_record_count={len(raw_records)}")
        print(f"raw_seen_counts={[record.seen_count for record in raw_records]}")
        print(f"raw_skill_statuses={[record.skill_sync_status.value for record in raw_records]}")
        print(f"job_post_count={job_count}")
        print(f"job_title={job_post.title if job_post is not None else None}")
        print(f"job_salary={job_post.salary_text if job_post is not None else None}")
        print(f"job_skills={skill_names}")

        if len(raw_records) != 2 or job_count != 1 or job_post is None:
            raise RuntimeError("MQ ingestion verification failed: unexpected deduplication result")
        if job_post.salary_text != "30-40K":
            raise RuntimeError("MQ ingestion verification failed: changed content was not applied")
        if skill_names != ["FastAPI", "PostgreSQL", "Python", "RabbitMQ"]:
            raise RuntimeError("MQ ingestion verification failed: skills were not synchronized")
    finally:
        await resources.close()


if __name__ == "__main__":
    asyncio.run(main())
