from __future__ import annotations

import argparse
import asyncio
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.config import settings
from job_pilot.core.resources import build_database_only_resources
from job_pilot.core.search import SqlLikeSearchBackend
from job_pilot.modules.job_skills.models import Skill
from job_pilot.modules.job_skills.repository import SkillDictionaryRepository
from job_pilot.modules.knowledge.enums import (
    ContentSourceType,
    KnowledgePointLevel,
    KnowledgePointStatus,
)
from job_pilot.modules.knowledge.models import KnowledgePoint
from job_pilot.modules.questions.enums import (
    QuestionAnswerStatus,
    QuestionDifficulty,
    QuestionReviewStatus,
    QuestionSkillRelation,
    QuestionStatus,
    QuestionType,
)
from job_pilot.modules.questions.models import (
    Question,
    QuestionAnswer,
    QuestionOption,
    QuestionSkill,
)

ImportSection = Literal["all", "skills", "knowledge", "questions"]


@dataclass(slots=True, frozen=True)
class SkillSeedItem:
    """脚本内技能字典样本，后续可迁移为后台管理导入参数。"""

    name: str
    aliases: list[str]


@dataclass(slots=True, frozen=True)
class KnowledgeSeedItem:
    """知识点树节点样本，path 用于表达父子层级。"""

    skill_name: str
    path: tuple[str, ...]
    summary: str
    level: KnowledgePointLevel
    sort_order: int
    source_note: str = "JobPilot MVP sample"


@dataclass(slots=True, frozen=True)
class QuestionOptionSeedItem:
    """选择题选项样本。"""

    option_label: str
    content: str
    is_correct: bool
    sort_order: int
    explanation: str | None = None


@dataclass(slots=True, frozen=True)
class QuestionSeedItem:
    """题目样本，当前只导入公共官方题库内容。"""

    title: str
    question_text: str
    answer: str
    skill_name: str
    knowledge_path: tuple[str, ...]
    question_type: QuestionType = QuestionType.INTERVIEW_OPEN
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    options: list[QuestionOptionSeedItem] | None = None
    source_note: str = "JobPilot MVP sample"


@dataclass(slots=True, frozen=True)
class ImportStats:
    """导入统计。"""

    created_skills: int = 0
    created_aliases: int = 0
    created_knowledge_points: int = 0
    created_questions: int = 0
    created_answers: int = 0
    created_options: int = 0
    created_question_links: int = 0

    def merge(self, other: ImportStats) -> ImportStats:
        """合并多段导入统计。"""

        return ImportStats(
            created_skills=self.created_skills + other.created_skills,
            created_aliases=self.created_aliases + other.created_aliases,
            created_knowledge_points=(
                self.created_knowledge_points + other.created_knowledge_points
            ),
            created_questions=self.created_questions + other.created_questions,
            created_answers=self.created_answers + other.created_answers,
            created_options=self.created_options + other.created_options,
            created_question_links=self.created_question_links + other.created_question_links,
        )


DEFAULT_SKILLS: list[SkillSeedItem] = [
    SkillSeedItem(name="Python", aliases=["python", "py"]),
    SkillSeedItem(name="FastAPI", aliases=["fastapi"]),
    SkillSeedItem(name="SQLAlchemy", aliases=["sqlalchemy", "sqlalchemy2"]),
    SkillSeedItem(name="PostgreSQL", aliases=["postgresql", "postgres", "pgsql", "pg"]),
    SkillSeedItem(name="Redis", aliases=["redis"]),
    SkillSeedItem(name="Celery", aliases=["celery"]),
    SkillSeedItem(name="JWT", aliases=["jwt", "jsonwebtokens", "jsonwebtoken"]),
    SkillSeedItem(name="Docker", aliases=["docker"]),
    SkillSeedItem(name="pytest", aliases=["pytest", "py.test"]),
]

DEFAULT_KNOWLEDGE_POINTS: list[KnowledgeSeedItem] = [
    KnowledgeSeedItem(
        skill_name="Python",
        path=("Python 基础",),
        summary="数据结构、函数、异常、上下文管理器和类型注解等后端开发基础。",
        level=KnowledgePointLevel.BASIC,
        sort_order=10,
    ),
    KnowledgeSeedItem(
        skill_name="Python",
        path=("Python 基础", "异步编程"),
        summary="理解 async、await、事件循环和异步 I/O 的适用边界。",
        level=KnowledgePointLevel.INTERMEDIATE,
        sort_order=20,
    ),
    KnowledgeSeedItem(
        skill_name="FastAPI",
        path=("FastAPI Web 基础",),
        summary="路由、依赖注入、Pydantic 模型和异常处理的基础用法。",
        level=KnowledgePointLevel.BASIC,
        sort_order=10,
    ),
    KnowledgeSeedItem(
        skill_name="FastAPI",
        path=("FastAPI Web 基础", "Depends 依赖注入"),
        summary="通过 Depends 组织认证、数据库会话和用户上下文。",
        level=KnowledgePointLevel.INTERMEDIATE,
        sort_order=20,
    ),
    KnowledgeSeedItem(
        skill_name="SQLAlchemy",
        path=("SQLAlchemy ORM",),
        summary="SQLAlchemy 2.0 ORM 映射、Session、关系和查询表达式。",
        level=KnowledgePointLevel.INTERMEDIATE,
        sort_order=10,
    ),
    KnowledgeSeedItem(
        skill_name="SQLAlchemy",
        path=("SQLAlchemy ORM", "事务与并发"),
        summary="事务边界、flush、commit、rollback 与唯一约束冲突处理。",
        level=KnowledgePointLevel.INTERMEDIATE,
        sort_order=20,
    ),
    KnowledgeSeedItem(
        skill_name="PostgreSQL",
        path=("PostgreSQL 数据建模",),
        summary="唯一约束、索引、JSONB、外键和查询优化的工程化使用。",
        level=KnowledgePointLevel.INTERMEDIATE,
        sort_order=10,
    ),
    KnowledgeSeedItem(
        skill_name="Redis",
        path=("Redis 缓存",),
        summary="Cache Aside、缓存失效、热点数据和分布式锁基础。",
        level=KnowledgePointLevel.INTERMEDIATE,
        sort_order=10,
    ),
    KnowledgeSeedItem(
        skill_name="Celery",
        path=("Celery 异步任务",),
        summary="任务队列、重试、幂等和后台任务状态记录。",
        level=KnowledgePointLevel.INTERMEDIATE,
        sort_order=10,
    ),
    KnowledgeSeedItem(
        skill_name="JWT",
        path=("JWT 认证",),
        summary="access token、refresh token、过期时间、撤销和用户禁用校验。",
        level=KnowledgePointLevel.INTERMEDIATE,
        sort_order=10,
    ),
    KnowledgeSeedItem(
        skill_name="Docker",
        path=("Docker 部署",),
        summary="Dockerfile、Docker Compose、环境变量和服务编排。",
        level=KnowledgePointLevel.BASIC,
        sort_order=10,
    ),
    KnowledgeSeedItem(
        skill_name="pytest",
        path=("pytest 测试",),
        summary="fixture、AAA 原则、接口测试和异步测试组织方式。",
        level=KnowledgePointLevel.BASIC,
        sort_order=10,
    ),
]

DEFAULT_QUESTIONS: list[QuestionSeedItem] = [
    QuestionSeedItem(
        title="Python 中 list、tuple、dict 的适用场景",
        question_text=(
            "请说明 Python 中 list、tuple、dict 的核心区别，并结合后端业务举例说明适用场景。"
        ),
        answer=(
            "list 适合有序且可变的数据集合；tuple 适合不可变结构和固定字段组合；"
            "dict 适合通过 key 快速访问结构化数据。后端开发中，列表常用于结果集，"
            "元组可用于不可变查询条件，字典常用于 JSON payload 或映射关系。"
        ),
        skill_name="Python",
        knowledge_path=("Python 基础",),
        difficulty=QuestionDifficulty.EASY,
    ),
    QuestionSeedItem(
        title="async 和 await 解决什么问题",
        question_text="FastAPI 项目中为什么会使用 async 和 await？它们适合解决什么类型的问题？",
        answer=(
            "async/await 主要用于 I/O 密集型场景，让单个线程在等待数据库、网络或缓存响应时"
            "切换执行其他协程。它不能直接提升 CPU 密集型任务性能，CPU 密集任务更适合进程池"
            "或后台任务系统。"
        ),
        skill_name="Python",
        knowledge_path=("Python 基础", "异步编程"),
        difficulty=QuestionDifficulty.MEDIUM,
    ),
    QuestionSeedItem(
        title="FastAPI Depends 的作用",
        question_text="请解释 FastAPI Depends 的作用，并说明它在认证鉴权和数据库会话管理中的价值。",
        answer=(
            "Depends 用于声明式注入依赖，让路由函数只关注业务输入。认证场景中可以统一解析 token "
            "并返回当前用户；数据库场景中可以统一创建和释放会话，从而减少重复代码并保持请求边界清晰。"
        ),
        skill_name="FastAPI",
        knowledge_path=("FastAPI Web 基础", "Depends 依赖注入"),
        difficulty=QuestionDifficulty.MEDIUM,
    ),
    QuestionSeedItem(
        title="SQLAlchemy flush 和 commit 的区别",
        question_text=(
            "SQLAlchemy 中 flush 和 commit 有什么区别？为什么 service 中常常需要先 flush？"
        ),
        answer=(
            "flush 会把当前 Session 中的变更发送到数据库，但事务仍未提交；commit 会提交事务并使变更"
            "对其他事务可见。先 flush 可以提前获得自增主键、触发约束检查，"
            "并在同一事务内继续写入依赖数据。"
        ),
        skill_name="SQLAlchemy",
        knowledge_path=("SQLAlchemy ORM", "事务与并发"),
        difficulty=QuestionDifficulty.MEDIUM,
    ),
    QuestionSeedItem(
        title="PostgreSQL 唯一约束和幂等导入",
        question_text=(
            "为什么导入脚本需要依赖唯一约束或稳定查询条件来保证幂等？请结合 PostgreSQL 说明。"
        ),
        answer=(
            "幂等导入要求同一份数据重复执行不会产生重复记录。PostgreSQL 唯一约束可以从数据库层防止"
            "重复事实写入；脚本层再根据业务唯一键查询并更新已有记录，可以让导入过程同时具备补齐和修正能力。"
        ),
        skill_name="PostgreSQL",
        knowledge_path=("PostgreSQL 数据建模",),
        difficulty=QuestionDifficulty.MEDIUM,
    ),
    QuestionSeedItem(
        title="Redis Cache Aside 模式",
        question_text="什么是 Cache Aside 模式？写操作后为什么通常要删除缓存而不是直接更新缓存？",
        answer=(
            "Cache Aside 由业务代码先查缓存，未命中再查数据库并回填缓存。写操作后删除缓存可以降低"
            "缓存与数据库不一致的风险，后续读请求会重新从数据库加载最新事实。"
        ),
        skill_name="Redis",
        knowledge_path=("Redis 缓存",),
        difficulty=QuestionDifficulty.MEDIUM,
    ),
    QuestionSeedItem(
        title="Celery 任务为什么要设计幂等",
        question_text="Celery 后台任务为什么要考虑幂等？请结合失败重试和重复投递说明。",
        answer=(
            "消息队列和 worker 在网络抖动、进程重启或超时重试时可能重复执行同一任务。"
            "任务如果不幂等，可能重复创建记录或重复扣减状态。"
            "通过唯一约束、任务状态表和稳定 source_key 可以降低重复执行风险。"
        ),
        skill_name="Celery",
        knowledge_path=("Celery 异步任务",),
        difficulty=QuestionDifficulty.MEDIUM,
    ),
    QuestionSeedItem(
        title="JWT access token 和 refresh token 的分工",
        question_text=(
            "JWT 认证中 access token 和 refresh token 各自解决什么问题？"
            "为什么 refresh token 通常需要可撤销？"
        ),
        answer=(
            "access token 生命周期短，用于访问接口；"
            "refresh token 生命周期更长，用于换取新的 access token。"
            "refresh token 如果泄露影响更大，因此需要服务端保存会话或令牌标识，"
            "支持退出登录、禁用用户和风险撤销。"
        ),
        skill_name="JWT",
        knowledge_path=("JWT 认证",),
        difficulty=QuestionDifficulty.MEDIUM,
    ),
    QuestionSeedItem(
        title="Docker Compose 在后端项目中的价值",
        question_text=(
            "Docker Compose 对 FastAPI、PostgreSQL、Redis、Celery 这类后端项目有什么价值？"
        ),
        answer=(
            "Docker Compose 可以把 API、数据库、缓存和 worker 编排成一致的本地环境，"
            "减少手工安装差异，"
            "也便于验证服务依赖、环境变量和启动顺序。"
        ),
        skill_name="Docker",
        knowledge_path=("Docker 部署",),
        difficulty=QuestionDifficulty.EASY,
    ),
    QuestionSeedItem(
        title="pytest fixture 的作用",
        question_text="pytest fixture 解决了什么问题？在接口测试中如何用 fixture 保持 AAA 原则？",
        answer=(
            "fixture 用于准备和清理测试依赖，例如数据库会话、测试用户和 HTTP 客户端。"
            "接口测试中可以把"
            "Arrange 阶段的公共准备逻辑放入 fixture，让测试主体清晰表达 Act 和 Assert。"
        ),
        skill_name="pytest",
        knowledge_path=("pytest 测试",),
        difficulty=QuestionDifficulty.EASY,
    ),
    QuestionSeedItem(
        title="判断题：Cache Aside 写操作后必须同步更新缓存",
        question_text="Cache Aside 模式下，写操作后必须同步更新缓存，否则一定会读到脏数据。",
        answer="错误。常见做法是写数据库后删除相关缓存，让下一次读取从数据库重新加载。",
        skill_name="Redis",
        knowledge_path=("Redis 缓存",),
        question_type=QuestionType.TRUE_FALSE,
        difficulty=QuestionDifficulty.EASY,
        options=[
            QuestionOptionSeedItem(
                option_label="True",
                content="正确",
                is_correct=False,
                sort_order=10,
                explanation="写后同步更新缓存不是 Cache Aside 的唯一做法，也可能引入并发不一致。",
            ),
            QuestionOptionSeedItem(
                option_label="False",
                content="错误",
                is_correct=True,
                sort_order=20,
                explanation="写数据库后删除缓存是 Cache Aside 中常见且更稳妥的策略。",
            ),
        ],
    ),
]


async def import_default_skills(session: AsyncSession) -> ImportStats:
    """导入默认技能字典和别名。"""

    repository = SkillDictionaryRepository(SqlLikeSearchBackend())
    created_skill_count = 0
    created_alias_count = 0

    for item in DEFAULT_SKILLS:
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

    await session.flush()
    return ImportStats(
        created_skills=created_skill_count,
        created_aliases=created_alias_count,
    )


async def import_default_knowledge_points(session: AsyncSession) -> ImportStats:
    """导入默认知识点树，要求对应技能已存在。"""

    skill_map = await _load_skill_map(session)
    created_count = 0
    point_map: dict[tuple[str, tuple[str, ...]], KnowledgePoint] = {}

    for item in DEFAULT_KNOWLEDGE_POINTS:
        skill = _require_skill(skill_map, item.skill_name)
        parent = _find_parent_point(point_map, item)
        point, created = await _upsert_knowledge_point(
            session=session,
            item=item,
            skill_id=skill.id,
            parent=parent,
        )
        point_map[(item.skill_name, item.path)] = point
        if created:
            created_count += 1

    await session.flush()
    return ImportStats(created_knowledge_points=created_count)


async def import_default_questions(session: AsyncSession) -> ImportStats:
    """导入默认题目、官方答案、选项和题目技能关系。"""

    skill_map = await _load_skill_map(session)
    knowledge_map = await _load_knowledge_point_map(session)
    stats = ImportStats()

    for item in DEFAULT_QUESTIONS:
        skill = _require_skill(skill_map, item.skill_name)
        knowledge_point = _require_knowledge_point(knowledge_map, item)
        question, created_question = await _upsert_question(session=session, item=item)
        created_answer = await _upsert_official_answer(
            session=session,
            question_id=question.id,
            item=item,
        )
        created_options = await _replace_question_options(
            session=session,
            question_id=question.id,
            options=item.options or [],
        )
        created_link = await _upsert_primary_question_skill(
            session=session,
            question_id=question.id,
            skill_id=skill.id,
            knowledge_point_id=knowledge_point.id,
        )

        stats = stats.merge(
            ImportStats(
                created_questions=1 if created_question else 0,
                created_answers=1 if created_answer else 0,
                created_options=created_options,
                created_question_links=1 if created_link else 0,
            )
        )

    await session.flush()
    return stats


async def import_learning_samples(section: ImportSection = "all") -> ImportStats:
    """按指定范围导入学习准备模块的示例数据。"""

    resources = build_database_only_resources(settings)
    try:
        async with resources.require_database().session_factory() as session:
            stats = await _import_with_session(session=session, section=section)
            await session.commit()
            return stats
    finally:
        await resources.close()


async def _import_with_session(
    *,
    session: AsyncSession,
    section: ImportSection,
) -> ImportStats:
    """在单个事务中按依赖顺序导入样本数据。"""

    stats = ImportStats()

    if section in {"all", "skills"}:
        stats = stats.merge(await import_default_skills(session))
    if section in {"all", "knowledge"}:
        if section == "knowledge":
            stats = stats.merge(await import_default_skills(session))
        stats = stats.merge(await import_default_knowledge_points(session))
    if section in {"all", "questions"}:
        if section == "questions":
            stats = stats.merge(await import_default_skills(session))
            stats = stats.merge(await import_default_knowledge_points(session))
        stats = stats.merge(await import_default_questions(session))

    return stats


async def main() -> None:
    """命令行入口。"""

    args = parse_args()
    stats = await import_learning_samples(section=args.section)
    print(
        "Imported learning samples: "
        f"skills={stats.created_skills}, aliases={stats.created_aliases}, "
        f"knowledge_points={stats.created_knowledge_points}, "
        f"questions={stats.created_questions}, answers={stats.created_answers}, "
        f"options={stats.created_options}, question_links={stats.created_question_links}"
    )


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="Import JobPilot MVP learning sample data.",
    )
    parser.add_argument(
        "--section",
        choices=("all", "skills", "knowledge", "questions"),
        default="all",
        help="Import scope. knowledge/questions will also ensure prerequisite skills.",
    )
    return parser.parse_args()


def build_question_hash(question_text: str) -> str:
    """生成题干去重 hash。"""

    normalized_text = normalize_question_text(question_text)
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def normalize_question_text(question_text: str) -> str:
    """清洗题干用于稳定去重。"""

    return " ".join(question_text.casefold().split())


async def _load_skill_map(session: AsyncSession) -> dict[str, Skill]:
    result = await session.execute(select(Skill))
    skills = list(result.scalars().all())
    return {skill.name: skill for skill in skills}


async def _load_knowledge_point_map(
    session: AsyncSession,
) -> dict[tuple[str, tuple[str, ...]], KnowledgePoint]:
    result = await session.execute(
        select(KnowledgePoint, Skill.name)
        .join(Skill, Skill.id == KnowledgePoint.skill_id)
        .order_by(Skill.name.asc(), KnowledgePoint.depth.asc(), KnowledgePoint.sort_order.asc())
    )
    rows = result.all()
    point_by_id: dict[int, KnowledgePoint] = {}
    path_by_id: dict[int, tuple[str, ...]] = {}
    knowledge_map: dict[tuple[str, tuple[str, ...]], KnowledgePoint] = {}

    for point, _skill_name in rows:
        point_by_id[point.id] = point

    for point, skill_name in rows:
        path = _build_loaded_knowledge_path(point=point, path_by_id=path_by_id)
        path_by_id[point.id] = path
        knowledge_map[(skill_name, path)] = point

    return knowledge_map


def _build_loaded_knowledge_path(
    *,
    point: KnowledgePoint,
    path_by_id: dict[int, tuple[str, ...]],
) -> tuple[str, ...]:
    if point.parent_id is None:
        return (point.title,)
    parent_path = path_by_id.get(point.parent_id)
    if parent_path is None:
        return (point.title,)
    return (*parent_path, point.title)


def _require_skill(skill_map: dict[str, Skill], skill_name: str) -> Skill:
    skill = skill_map.get(skill_name)
    if skill is None:
        raise ValueError(f"Missing skill: {skill_name}")
    return skill


def _find_parent_point(
    point_map: dict[tuple[str, tuple[str, ...]], KnowledgePoint],
    item: KnowledgeSeedItem,
) -> KnowledgePoint | None:
    if len(item.path) == 1:
        return None
    parent_path = item.path[:-1]
    parent = point_map.get((item.skill_name, parent_path))
    if parent is None:
        raise ValueError(f"Missing parent knowledge point: {item.skill_name}/{parent_path}")
    return parent


async def _upsert_knowledge_point(
    *,
    session: AsyncSession,
    item: KnowledgeSeedItem,
    skill_id: int,
    parent: KnowledgePoint | None,
) -> tuple[KnowledgePoint, bool]:
    title = item.path[-1]
    stmt = select(KnowledgePoint).where(
        KnowledgePoint.skill_id == skill_id,
        KnowledgePoint.title == title,
    )
    if parent is None:
        stmt = stmt.where(KnowledgePoint.parent_id.is_(None))
    else:
        stmt = stmt.where(KnowledgePoint.parent_id == parent.id)

    result = await session.execute(stmt.limit(1))
    point = result.scalar_one_or_none()
    created = point is None

    if point is None:
        point = KnowledgePoint(
            skill_id=skill_id,
            parent_id=parent.id if parent is not None else None,
            title=title,
            summary=item.summary,
            level=item.level,
            depth=len(item.path) - 1,
            sort_order=item.sort_order,
            status=KnowledgePointStatus.ACTIVE,
        )
        session.add(point)
    else:
        point.summary = item.summary
        point.level = item.level
        point.depth = len(item.path) - 1
        point.sort_order = item.sort_order
        point.status = KnowledgePointStatus.ACTIVE

    await session.flush()
    return point, created


def _require_knowledge_point(
    knowledge_map: dict[tuple[str, tuple[str, ...]], KnowledgePoint],
    item: QuestionSeedItem,
) -> KnowledgePoint:
    knowledge_point = knowledge_map.get((item.skill_name, item.knowledge_path))
    if knowledge_point is None:
        raise ValueError(
            f"Missing knowledge point: {item.skill_name}/{'/'.join(item.knowledge_path)}"
        )
    return knowledge_point


async def _upsert_question(
    *,
    session: AsyncSession,
    item: QuestionSeedItem,
) -> tuple[Question, bool]:
    question_hash = build_question_hash(item.question_text)
    result = await session.execute(
        select(Question).where(Question.question_hash == question_hash).limit(1)
    )
    question = result.scalar_one_or_none()
    created = question is None

    if question is None:
        question = Question(
            title=item.title,
            question_text=item.question_text,
            question_hash=question_hash,
            question_type=item.question_type,
            difficulty=item.difficulty,
            status=QuestionStatus.ACTIVE,
            source_type=ContentSourceType.OFFICIAL,
            source_note=item.source_note,
            review_status=QuestionReviewStatus.APPROVED,
            created_by_user_id=None,
        )
        session.add(question)
    else:
        question.title = item.title
        question.question_text = item.question_text
        question.question_type = item.question_type
        question.difficulty = item.difficulty
        question.status = QuestionStatus.ACTIVE
        question.source_type = ContentSourceType.OFFICIAL
        question.source_note = item.source_note
        question.review_status = QuestionReviewStatus.APPROVED
        question.created_by_user_id = None

    await session.flush()
    return question, created


async def _upsert_official_answer(
    *,
    session: AsyncSession,
    question_id: int,
    item: QuestionSeedItem,
) -> bool:
    result = await session.execute(
        select(QuestionAnswer)
        .where(
            QuestionAnswer.question_id == question_id,
            QuestionAnswer.source_type == ContentSourceType.OFFICIAL,
        )
        .limit(1)
    )
    answer = result.scalar_one_or_none()
    created = answer is None

    if answer is None:
        answer = QuestionAnswer(
            question_id=question_id,
            content=item.answer,
            source_type=ContentSourceType.OFFICIAL,
            status=QuestionAnswerStatus.ACTIVE,
            created_by_user_id=None,
        )
        session.add(answer)
    else:
        answer.content = item.answer
        answer.status = QuestionAnswerStatus.ACTIVE
        answer.created_by_user_id = None

    await session.flush()
    return created


async def _replace_question_options(
    *,
    session: AsyncSession,
    question_id: int,
    options: Sequence[QuestionOptionSeedItem],
) -> int:
    result = await session.execute(
        select(QuestionOption)
        .where(QuestionOption.question_id == question_id)
        .order_by(QuestionOption.sort_order.asc(), QuestionOption.id.asc())
    )
    existing_options = list(result.scalars().all())
    existing_by_label = {option.option_label: option for option in existing_options}

    for index, option in enumerate(existing_options, start=1):
        option.sort_order = 100_000 + index
    await session.flush()

    seed_labels = {item.option_label for item in options}
    for option in existing_options:
        if option.option_label not in seed_labels:
            await session.delete(option)
    await session.flush()

    created_count = 0
    for item in options:
        option = existing_by_label.get(item.option_label)
        if option is None:
            option = QuestionOption(
                question_id=question_id,
                option_label=item.option_label,
                content=item.content,
                is_correct=item.is_correct,
                explanation=item.explanation,
                sort_order=item.sort_order,
            )
            session.add(option)
            created_count += 1
        else:
            option.content = item.content
            option.is_correct = item.is_correct
            option.explanation = item.explanation
            option.sort_order = item.sort_order

    await session.flush()
    return created_count


async def _upsert_primary_question_skill(
    *,
    session: AsyncSession,
    question_id: int,
    skill_id: int,
    knowledge_point_id: int,
) -> bool:
    knowledge_point = await session.get(KnowledgePoint, knowledge_point_id)
    if knowledge_point is None:
        raise ValueError(f"Missing knowledge point id: {knowledge_point_id}")
    if knowledge_point.skill_id != skill_id:
        raise ValueError(
            "Question skill link mismatch: "
            f"skill_id={skill_id}, knowledge_point_id={knowledge_point_id}"
        )

    result = await session.execute(
        select(QuestionSkill)
        .where(
            QuestionSkill.question_id == question_id,
            QuestionSkill.relation == QuestionSkillRelation.PRIMARY,
        )
        .limit(1)
    )
    question_skill = result.scalar_one_or_none()
    created = question_skill is None

    if question_skill is None:
        question_skill = QuestionSkill(
            question_id=question_id,
            skill_id=skill_id,
            knowledge_point_id=knowledge_point_id,
            relation=QuestionSkillRelation.PRIMARY,
        )
        session.add(question_skill)
    else:
        question_skill.skill_id = skill_id
        question_skill.knowledge_point_id = knowledge_point_id
        question_skill.relation = QuestionSkillRelation.PRIMARY

    await session.flush()
    return created


if __name__ == "__main__":
    asyncio.run(main())
