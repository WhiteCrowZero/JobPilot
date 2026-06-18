# ruff: noqa: E501
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.config import settings
from job_pilot.core.resources import build_database_only_resources
from job_pilot.modules.job_skills.repository import SkillDictionaryRepository


@dataclass(slots=True, frozen=True)
class SkillSeedItem:
    """脚本内默认技能种子，不进入正式 service 契约。"""

    name: str
    aliases: list[str]


DEFAULT_SKILL_DICTIONARY: list[SkillSeedItem] = [
    SkillSeedItem(name="Python", aliases=["python", "py"]),
    SkillSeedItem(name="Java", aliases=["java"]),
    SkillSeedItem(name="Go", aliases=["go", "golang"]),
    SkillSeedItem(name="JavaScript", aliases=["javascript", "js"]),
    SkillSeedItem(name="TypeScript", aliases=["typescript", "ts"]),
    SkillSeedItem(name="SQL", aliases=["sql"]),
    SkillSeedItem(name="FastAPI", aliases=["fastapi"]),
    SkillSeedItem(name="Django", aliases=["django"]),
    SkillSeedItem(name="Django REST Framework", aliases=["djangorestframework", "drf"]),
    SkillSeedItem(name="Flask", aliases=["flask"]),
    SkillSeedItem(name="Spring Boot", aliases=["springboot"]),
    SkillSeedItem(name="Node.js", aliases=["node.js", "nodejs", "node"]),
    SkillSeedItem(name="Vue", aliases=["vue", "vue.js", "vuejs"]),
    SkillSeedItem(name="React", aliases=["react", "react.js", "reactjs"]),
    SkillSeedItem(name="MySQL", aliases=["mysql"]),
    SkillSeedItem(name="PostgreSQL", aliases=["postgresql", "postgres", "pgsql", "pg"]),
    SkillSeedItem(name="MongoDB", aliases=["mongodb", "mongo"]),
    SkillSeedItem(name="Elasticsearch", aliases=["elasticsearch", "es"]),
    SkillSeedItem(name="Redis", aliases=["redis"]),
    SkillSeedItem(name="RabbitMQ", aliases=["rabbitmq"]),
    SkillSeedItem(name="Kafka", aliases=["kafka", "apachekafka"]),
    SkillSeedItem(name="Celery", aliases=["celery"]),
    SkillSeedItem(name="Docker", aliases=["docker"]),
    SkillSeedItem(name="Docker Compose", aliases=["dockercompose"]),
    SkillSeedItem(name="Kubernetes", aliases=["kubernetes", "k8s"]),
    SkillSeedItem(name="Linux", aliases=["linux"]),
    SkillSeedItem(name="Git", aliases=["git"]),
    SkillSeedItem(name="GitHub Actions", aliases=["githubactions", "githubaction"]),
    SkillSeedItem(name="pytest", aliases=["pytest", "py.test"]),
    SkillSeedItem(name="SQLAlchemy", aliases=["sqlalchemy"]),
    SkillSeedItem(name="Pydantic", aliases=["pydantic"]),
    SkillSeedItem(name="Alembic", aliases=["alembic"]),
    SkillSeedItem(name="Nginx", aliases=["nginx"]),
    SkillSeedItem(name="AWS", aliases=["aws", "amazonwebservices"]),
    SkillSeedItem(name="Azure", aliases=["azure"]),
    SkillSeedItem(name="GCP", aliases=["gcp", "googlecloud"]),
    SkillSeedItem(name="REST API", aliases=["rest", "restful", "restapi"]),
    SkillSeedItem(name="WebSocket", aliases=["websocket"]),
    SkillSeedItem(name="Microservices", aliases=["microservices", "微服务"]),
    SkillSeedItem(name="Message Queue", aliases=["messagequeue", "消息队列", "mq"]),
]


async def seed_default_skills(session: AsyncSession) -> tuple[int, int]:
    """初始化默认技能字典，重复执行时只补齐缺失记录。"""

    repository = SkillDictionaryRepository()
    created_skill_count = 0
    created_alias_count = 0

    for item in DEFAULT_SKILL_DICTIONARY:
        skill, created_skill = await repository.upsert_skill(db=session, name=item.name)
        if created_skill:
            created_skill_count += 1

        for alias in item.aliases:
            created_alias = await repository.upsert_alias(
                db=session,
                skill_id=skill.id,
                alias=alias,
            )
            if created_alias:
                created_alias_count += 1

    return created_skill_count, created_alias_count


async def main() -> None:
    """独立运行默认技能种子脚本。"""

    resources = build_database_only_resources(settings)
    try:
        async with resources.require_database().session_factory() as session:
            created_skills, created_aliases = await seed_default_skills(session)
            await session.commit()
            print(f"Created {created_skills} skills and {created_aliases} aliases")
    finally:
        await resources.close()


if __name__ == "__main__":
    asyncio.run(main())
