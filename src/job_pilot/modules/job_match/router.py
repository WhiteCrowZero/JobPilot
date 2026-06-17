from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from job_pilot.api.deps import CurrentActiveUserDep, JobPilotDep
from job_pilot.modules.job_match.contracts import (
    JobSkillCoverageResult,
    SkillCoverageResultItem,
    TargetSkillSummaryResult,
    TargetSkillSummaryResultItem,
)
from job_pilot.modules.job_match.schemas import (
    JobSkillCoverageResponse,
    SkillCoverageItem,
    TargetSkillSummaryItem,
    TargetSkillSummaryResponse,
)
from job_pilot.modules.job_match.service import DEFAULT_REQUIRED_LEVEL

router = APIRouter()


@router.get("/jobs/{job_post_id}/coverage", response_model=JobSkillCoverageResponse)
async def analyze_job_skill_coverage(
    job_post_id: int,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
    required_level: Annotated[int, Query(ge=1, le=5)] = DEFAULT_REQUIRED_LEVEL,
) -> JobSkillCoverageResponse:
    """分析当前用户对某个岗位技能标签的覆盖情况。"""

    result = await pilot.workbench.analyze_job_skill_coverage(
        user_id=current_user.id,
        job_post_id=job_post_id,
        required_level=required_level,
    )
    return _to_job_skill_coverage_response(result)


@router.get("/targets/{target_id}/coverage", response_model=JobSkillCoverageResponse)
async def analyze_target_skill_coverage(
    target_id: int,
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
    required_level: Annotated[int, Query(ge=1, le=5)] = DEFAULT_REQUIRED_LEVEL,
) -> JobSkillCoverageResponse:
    """分析当前用户某个目标岗位的技能覆盖情况。"""

    result = await pilot.workbench.analyze_target_skill_coverage(
        user_id=current_user.id,
        target_id=target_id,
        required_level=required_level,
    )
    return _to_job_skill_coverage_response(result)


@router.get("/targets/skills", response_model=TargetSkillSummaryResponse)
async def analyze_target_skill_summary(
    current_user: CurrentActiveUserDep,
    pilot: JobPilotDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    required_level: Annotated[int, Query(ge=1, le=5)] = DEFAULT_REQUIRED_LEVEL,
) -> TargetSkillSummaryResponse:
    """统计当前 active/paused 目标岗位中高频出现的技能。"""

    result = await pilot.workbench.analyze_target_skill_summary(
        user_id=current_user.id,
        limit=limit,
        required_level=required_level,
    )
    return _to_target_skill_summary_response(result)


def _to_skill_coverage_item(item: SkillCoverageResultItem) -> SkillCoverageItem:
    """把 service 内部技能覆盖项转换为接口响应项。"""

    return SkillCoverageItem(
        skill_id=item.skill_id,
        skill_name=item.skill_name,
        status=item.status,
        required_level=item.required_level,
        user_proficiency_level=item.user_proficiency_level,
    )


def _to_job_skill_coverage_response(result: JobSkillCoverageResult) -> JobSkillCoverageResponse:
    """把 service 内部覆盖结果转换为接口响应。"""

    return JobSkillCoverageResponse(
        analysis_status=result.analysis_status,
        job_post_id=result.job_post_id,
        target_id=result.target_id,
        is_primary=result.is_primary,
        target_priority=result.target_priority,
        target_status=result.target_status,
        required_level=result.required_level,
        required_skill_count=result.required_skill_count,
        matched_count=result.matched_count,
        weak_count=result.weak_count,
        missing_count=result.missing_count,
        coverage_score=result.coverage_score,
        matched_skills=[_to_skill_coverage_item(item) for item in result.matched_skills],
        weak_skills=[_to_skill_coverage_item(item) for item in result.weak_skills],
        missing_skills=[_to_skill_coverage_item(item) for item in result.missing_skills],
    )


def _to_target_skill_summary_item(
    item: TargetSkillSummaryResultItem,
) -> TargetSkillSummaryItem:
    """把 service 内部目标技能摘要项转换为接口响应项。"""

    return TargetSkillSummaryItem(
        skill_id=item.skill_id,
        skill_name=item.skill_name,
        target_count=item.target_count,
        target_ratio=item.target_ratio,
        appears_in_primary_target=item.appears_in_primary_target,
        has_user_skill=item.has_user_skill,
        user_proficiency_level=item.user_proficiency_level,
        user_skill_status=item.user_skill_status,
    )


def _to_target_skill_summary_response(
    result: TargetSkillSummaryResult,
) -> TargetSkillSummaryResponse:
    """把 service 内部目标技能摘要转换为接口响应。"""

    return TargetSkillSummaryResponse(
        required_level=result.required_level,
        target_count=result.target_count,
        primary_target_id=result.primary_target_id,
        primary_job_post_id=result.primary_job_post_id,
        primary_target_skill_count=result.primary_target_skill_count,
        other_target_count=result.other_target_count,
        skill_count=result.skill_count,
        items=[_to_target_skill_summary_item(item) for item in result.items],
    )
