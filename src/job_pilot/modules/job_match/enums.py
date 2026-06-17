from __future__ import annotations

from enum import StrEnum


class JobMatchAnalysisStatus(StrEnum):
    """技能覆盖分析状态。"""

    ANALYZABLE = "analyzable"
    NO_JOB_SKILL_DATA = "no_job_skill_data"


class JobMatchSkillStatus(StrEnum):
    """用户技能相对岗位技能的覆盖状态。"""

    MATCHED = "matched"
    WEAK = "weak"
    MISSING = "missing"
