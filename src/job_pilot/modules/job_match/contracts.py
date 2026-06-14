from __future__ import annotations

from dataclasses import dataclass, field

from job_pilot.modules.job_match.enums import JobMatchAnalysisStatus, JobMatchSkillStatus
from job_pilot.modules.job_targets.enums import JobTargetStatus


@dataclass(frozen=True, slots=True)
class SkillCoverageResultItem:
    """技能覆盖分析的内部结果项。"""

    skill_id: int
    skill_name: str
    status: JobMatchSkillStatus
    required_level: int
    user_proficiency_level: int | None = None


@dataclass(frozen=True, slots=True)
class SkillCoverageBuckets:
    """技能集合分类结果。"""

    matched_skills: list[SkillCoverageResultItem]
    weak_skills: list[SkillCoverageResultItem]
    missing_skills: list[SkillCoverageResultItem]


@dataclass(frozen=True, slots=True)
class JobSkillCoverageResult:
    """单岗位或目标岗位技能覆盖分析的内部结果。"""

    analysis_status: JobMatchAnalysisStatus
    job_post_id: int
    required_level: int
    required_skill_count: int
    matched_count: int
    weak_count: int
    missing_count: int
    coverage_score: float | None
    target_id: int | None = None
    is_primary: bool | None = None
    target_priority: int | None = None
    target_status: JobTargetStatus | None = None
    matched_skills: list[SkillCoverageResultItem] = field(default_factory=list)
    weak_skills: list[SkillCoverageResultItem] = field(default_factory=list)
    missing_skills: list[SkillCoverageResultItem] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TargetSkillSummaryResultItem:
    """目标岗位技能摘要的内部结果项。"""

    skill_id: int
    skill_name: str
    target_count: int
    target_ratio: float
    appears_in_primary_target: bool
    has_user_skill: bool
    user_proficiency_level: int | None
    user_skill_status: JobMatchSkillStatus


@dataclass(frozen=True, slots=True)
class TargetSkillSummaryResult:
    """当前目标岗位集合技能摘要的内部结果。"""

    required_level: int
    target_count: int
    primary_target_id: int | None
    primary_job_post_id: int | None
    primary_target_skill_count: int
    other_target_count: int
    skill_count: int
    items: list[TargetSkillSummaryResultItem] = field(default_factory=list)
