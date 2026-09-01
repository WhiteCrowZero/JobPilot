from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RawSkillCandidate:
    """来源 raw 数据中可用于归一化的技能候选。"""

    text: str


@dataclass(slots=True, frozen=True)
class SkillAliasMatch:
    """raw skill 命中标准技能后的结果。"""

    skill_id: int
    skill_name: str


@dataclass(slots=True, frozen=True)
class SkillNormalizationResult:
    """技能候选归一化结果。"""

    matched: list[SkillAliasMatch]
    unmatched: list[str]


@dataclass(slots=True, frozen=True)
class SkillSyncResult:
    """岗位技能同步结果，供脚本、worker 和测试使用。"""

    job_post_id: int
    synced: bool
    skipped_reason: str | None
    created_count: int
    matched_count: int
    unmatched_texts: list[str]
