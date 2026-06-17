from __future__ import annotations

from pydantic import BaseModel, Field

from job_pilot.modules.job_match.enums import JobMatchAnalysisStatus, JobMatchSkillStatus
from job_pilot.modules.job_targets.enums import JobTargetStatus


class SkillCoverageItem(BaseModel):
    """技能覆盖分析中的单个技能项。"""

    skill_id: int
    skill_name: str
    status: JobMatchSkillStatus
    required_level: int = Field(ge=1, le=5)
    user_proficiency_level: int | None = Field(default=None, ge=1, le=5)


class JobSkillCoverageResponse(BaseModel):
    """单岗位或目标岗位的技能覆盖分析响应。"""

    analysis_status: JobMatchAnalysisStatus
    job_post_id: int
    target_id: int | None = None
    is_primary: bool | None = None
    target_priority: int | None = None
    target_status: JobTargetStatus | None = None

    required_level: int = Field(ge=1, le=5)
    required_skill_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    weak_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    coverage_score: float | None = Field(default=None, ge=0, le=1)

    matched_skills: list[SkillCoverageItem] = Field(default_factory=list)
    weak_skills: list[SkillCoverageItem] = Field(default_factory=list)
    missing_skills: list[SkillCoverageItem] = Field(default_factory=list)


class TargetSkillSummaryItem(BaseModel):
    """目标岗位技能统计项。"""

    skill_id: int
    skill_name: str
    target_count: int = Field(ge=0)
    target_ratio: float = Field(ge=0, le=1)
    appears_in_primary_target: bool

    has_user_skill: bool
    user_proficiency_level: int | None = Field(default=None, ge=1, le=5)
    user_skill_status: JobMatchSkillStatus


class TargetSkillSummaryResponse(BaseModel):
    """当前目标岗位集合中的技能统计摘要。"""

    required_level: int = Field(ge=1, le=5)
    target_count: int = Field(ge=0)
    primary_target_id: int | None = None
    primary_job_post_id: int | None = None
    primary_target_skill_count: int = Field(ge=0)
    other_target_count: int = Field(ge=0)
    skill_count: int = Field(ge=0)
    items: list[TargetSkillSummaryItem] = Field(default_factory=list)
