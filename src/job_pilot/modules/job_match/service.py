from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.exceptions import ValidationError
from job_pilot.modules.job_match.contracts import (
    JobSkillCoverageResult,
    SkillCoverageBuckets,
    SkillCoverageResultItem,
    TargetSkillSummaryResult,
    TargetSkillSummaryResultItem,
)
from job_pilot.modules.job_match.enums import JobMatchAnalysisStatus, JobMatchSkillStatus
from job_pilot.modules.job_match.exceptions import (
    JobPostForMatchNotFoundError,
    JobTargetForMatchNotFoundError,
)
from job_pilot.modules.job_match.repository import (
    JobMatchRepository,
    JobSkillSnapshot,
    JobTargetSnapshot,
    UserSkillSnapshot,
)

DEFAULT_REQUIRED_LEVEL = 3
DEFAULT_SUMMARY_LIMIT = 20
MAX_SUMMARY_LIMIT = 100


class JobMatchTextAnalyzer:
    """后续岗位描述分析扩展点；MVP 不启用。"""

    async def extract_skills_from_description(self, description: str) -> list[str]:
        """从岗位描述中抽取技能名称，后续接规则、AI 或 embedding。"""

        _ = description
        raise NotImplementedError("Job description skill extraction is reserved for later phases")


class JobMatchEmbeddingAnalyzer:
    """后续技能语义召回扩展点；MVP 不启用。"""

    async def search_related_skill_ids(self, skill_name: str, limit: int = 10) -> list[int]:
        """根据技能名称召回语义相关技能 ID，后续接 embedding。"""

        _ = skill_name
        _ = limit
        raise NotImplementedError("Skill embedding search is reserved for later phases")


class JobMatchService:
    """技能覆盖分析 service，只做可解释的集合计算。"""

    def __init__(self, repository: JobMatchRepository) -> None:
        self.repository = repository

    async def analyze_job_skill_coverage(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        job_post_id: int,
        required_level: int = DEFAULT_REQUIRED_LEVEL,
    ) -> JobSkillCoverageResult:
        """分析当前用户对某个岗位技能标签的覆盖情况。"""

        self._validate_required_level(required_level)
        if not await self.repository.job_post_exists(db, job_post_id=job_post_id):
            raise JobPostForMatchNotFoundError()

        job_skills = await self.repository.list_job_skills(db, job_post_id=job_post_id)
        target = await self.repository.get_current_target_for_job(
            db,
            user_id=user_id,
            job_post_id=job_post_id,
        )
        return await self._build_coverage_response(
            db,
            user_id=user_id,
            job_post_id=job_post_id,
            target=target,
            job_skills=job_skills,
            required_level=required_level,
        )

    async def analyze_target_skill_coverage(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        required_level: int = DEFAULT_REQUIRED_LEVEL,
    ) -> JobSkillCoverageResult:
        """分析当前用户某个目标岗位的技能覆盖情况。"""

        self._validate_required_level(required_level)
        target = await self.repository.get_user_target(db, user_id=user_id, target_id=target_id)
        if target is None:
            raise JobTargetForMatchNotFoundError()
        if not await self.repository.job_post_exists(db, job_post_id=target.job_post_id):
            raise JobPostForMatchNotFoundError()

        job_skills = await self.repository.list_job_skills(db, job_post_id=target.job_post_id)
        return await self._build_coverage_response(
            db,
            user_id=user_id,
            job_post_id=target.job_post_id,
            target=target,
            job_skills=job_skills,
            required_level=required_level,
        )

    async def analyze_target_skill_summary(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        limit: int = DEFAULT_SUMMARY_LIMIT,
        required_level: int = DEFAULT_REQUIRED_LEVEL,
    ) -> TargetSkillSummaryResult:
        """统计当前目标岗位集合中的高频技能摘要。"""

        self._validate_required_level(required_level)
        self._validate_limit(limit)
        current_targets = await self.repository.list_current_targets(db, user_id=user_id)
        primary_target = next((target for target in current_targets if target.is_primary), None)
        job_post_ids = [target.job_post_id for target in current_targets]
        summary_rows = await self.repository.list_skill_summary_for_jobs(
            db,
            job_post_ids=job_post_ids,
            limit=limit,
        )
        user_skills = await self.repository.list_user_active_skills(
            db,
            user_id=user_id,
            skill_ids=[row.skill_id for row in summary_rows],
        )
        user_skill_map = {user_skill.skill_id: user_skill for user_skill in user_skills}
        primary_skill_ids = await self._get_primary_target_skill_ids(db, primary_target)

        items = [
            self._to_summary_item(
                row_skill_id=row.skill_id,
                row_skill_name=row.skill_name,
                row_target_count=row.target_count,
                target_count=len(current_targets),
                user_skill=user_skill_map.get(row.skill_id),
                required_level=required_level,
                appears_in_primary_target=row.skill_id in primary_skill_ids,
            )
            for row in summary_rows
        ]
        return TargetSkillSummaryResult(
            required_level=required_level,
            target_count=len(current_targets),
            primary_target_id=primary_target.target_id if primary_target is not None else None,
            primary_job_post_id=primary_target.job_post_id if primary_target is not None else None,
            primary_target_skill_count=len(primary_skill_ids),
            other_target_count=self._count_other_targets(
                current_target_count=len(current_targets),
                primary_target=primary_target,
            ),
            skill_count=len(items),
            items=items,
        )

    async def _build_coverage_response(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        job_post_id: int,
        target: JobTargetSnapshot | None,
        job_skills: list[JobSkillSnapshot],
        required_level: int,
    ) -> JobSkillCoverageResult:
        """根据岗位技能和用户技能构造覆盖分析响应。"""

        if not job_skills:
            return self._empty_coverage_response(
                job_post_id=job_post_id,
                target=target,
                required_level=required_level,
            )

        user_skills = await self.repository.list_user_active_skills(
            db,
            user_id=user_id,
            skill_ids=[skill.skill_id for skill in job_skills],
        )
        buckets = classify_skill_coverage(
            job_skills=job_skills,
            user_skills=user_skills,
            required_level=required_level,
        )
        required_skill_count = len(job_skills)
        matched_count = len(buckets.matched_skills)
        coverage_score = round(matched_count / required_skill_count, 4)
        return JobSkillCoverageResult(
            analysis_status=JobMatchAnalysisStatus.ANALYZABLE,
            job_post_id=job_post_id,
            target_id=target.target_id if target is not None else None,
            is_primary=target.is_primary if target is not None else None,
            target_priority=target.priority if target is not None else None,
            target_status=target.status if target is not None else None,
            required_level=required_level,
            required_skill_count=required_skill_count,
            matched_count=matched_count,
            weak_count=len(buckets.weak_skills),
            missing_count=len(buckets.missing_skills),
            coverage_score=coverage_score,
            matched_skills=buckets.matched_skills,
            weak_skills=buckets.weak_skills,
            missing_skills=buckets.missing_skills,
        )

    async def _get_primary_target_skill_ids(
        self,
        db: AsyncSession,
        primary_target: JobTargetSnapshot | None,
    ) -> set[int]:
        """读取主目标岗位技能 ID，用于频率统计结果标记。"""

        if primary_target is None:
            return set()
        primary_skills = await self.repository.list_job_skills(
            db,
            job_post_id=primary_target.job_post_id,
        )
        return {skill.skill_id for skill in primary_skills}

    @staticmethod
    def _count_other_targets(
        *,
        current_target_count: int,
        primary_target: JobTargetSnapshot | None,
    ) -> int:
        """计算非主目标数量。"""

        primary_count = 1 if primary_target is not None else 0
        return max(current_target_count - primary_count, 0)

    @staticmethod
    def _empty_coverage_response(
        *,
        job_post_id: int,
        target: JobTargetSnapshot | None,
        required_level: int,
    ) -> JobSkillCoverageResult:
        """岗位没有结构化技能数据时，不强行计算分数。"""

        return JobSkillCoverageResult(
            analysis_status=JobMatchAnalysisStatus.NO_JOB_SKILL_DATA,
            job_post_id=job_post_id,
            target_id=target.target_id if target is not None else None,
            is_primary=target.is_primary if target is not None else None,
            target_priority=target.priority if target is not None else None,
            target_status=target.status if target is not None else None,
            required_level=required_level,
            required_skill_count=0,
            matched_count=0,
            weak_count=0,
            missing_count=0,
            coverage_score=None,
        )

    @staticmethod
    def _to_summary_item(
        *,
        row_skill_id: int,
        row_skill_name: str,
        row_target_count: int,
        target_count: int,
        user_skill: UserSkillSnapshot | None,
        required_level: int,
        appears_in_primary_target: bool,
    ) -> TargetSkillSummaryResultItem:
        """把技能摘要聚合行转换为接口响应项。"""

        user_skill_status = _get_user_skill_status(
            user_skill=user_skill,
            required_level=required_level,
        )
        target_ratio = round(row_target_count / target_count, 4) if target_count > 0 else 0
        return TargetSkillSummaryResultItem(
            skill_id=row_skill_id,
            skill_name=row_skill_name,
            target_count=row_target_count,
            target_ratio=target_ratio,
            appears_in_primary_target=appears_in_primary_target,
            has_user_skill=user_skill is not None,
            user_proficiency_level=(
                user_skill.proficiency_level if user_skill is not None else None
            ),
            user_skill_status=user_skill_status,
        )

    @staticmethod
    def _validate_required_level(required_level: int) -> None:
        if required_level < 1 or required_level > 5:
            raise ValidationError("required_level must be between 1 and 5")

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit < 1 or limit > MAX_SUMMARY_LIMIT:
            raise ValidationError("limit must be between 1 and 100")


def classify_skill_coverage(
    *,
    job_skills: list[JobSkillSnapshot],
    user_skills: list[UserSkillSnapshot],
    required_level: int,
) -> SkillCoverageBuckets:
    """按集合交集和掌握等级把岗位技能分为 matched、weak、missing。"""

    JobMatchService._validate_required_level(required_level)
    user_skill_map = {user_skill.skill_id: user_skill for user_skill in user_skills}
    matched_skills: list[SkillCoverageResultItem] = []
    weak_skills: list[SkillCoverageResultItem] = []
    missing_skills: list[SkillCoverageResultItem] = []

    for job_skill in sorted(job_skills, key=lambda item: item.skill_name):
        user_skill = user_skill_map.get(job_skill.skill_id)
        status = _get_user_skill_status(user_skill=user_skill, required_level=required_level)
        item = SkillCoverageResultItem(
            skill_id=job_skill.skill_id,
            skill_name=job_skill.skill_name,
            status=status,
            required_level=required_level,
            user_proficiency_level=(
                user_skill.proficiency_level if user_skill is not None else None
            ),
        )
        if status == JobMatchSkillStatus.MATCHED:
            matched_skills.append(item)
        elif status == JobMatchSkillStatus.WEAK:
            weak_skills.append(item)
        else:
            missing_skills.append(item)

    return SkillCoverageBuckets(
        matched_skills=matched_skills,
        weak_skills=weak_skills,
        missing_skills=missing_skills,
    )


def _get_user_skill_status(
    *,
    user_skill: UserSkillSnapshot | None,
    required_level: int,
) -> JobMatchSkillStatus:
    """根据用户技能是否存在和等级判断覆盖状态。"""

    if user_skill is None:
        return JobMatchSkillStatus.MISSING
    if user_skill.proficiency_level < required_level:
        return JobMatchSkillStatus.WEAK
    return JobMatchSkillStatus.MATCHED


def build_job_match_service() -> JobMatchService:
    """组装技能覆盖分析 service 的默认依赖。"""

    return JobMatchService(repository=JobMatchRepository())
