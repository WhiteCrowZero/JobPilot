from __future__ import annotations

from job_pilot.modules.job_match.enums import JobMatchSkillStatus
from job_pilot.modules.job_match.repository import JobSkillSnapshot, UserSkillSnapshot
from job_pilot.modules.job_match.service import classify_skill_coverage


def test_classify_skill_coverage_splits_matched_weak_and_missing() -> None:
    """技能覆盖分类纯逻辑不依赖数据库。"""

    job_skills = [
        JobSkillSnapshot(skill_id=1, skill_name="Python"),
        JobSkillSnapshot(skill_id=2, skill_name="Redis"),
        JobSkillSnapshot(skill_id=3, skill_name="MySQL"),
    ]
    user_skills = [
        UserSkillSnapshot(skill_id=1, skill_name="Python", proficiency_level=4),
        UserSkillSnapshot(skill_id=2, skill_name="Redis", proficiency_level=2),
    ]

    result = classify_skill_coverage(
        job_skills=job_skills,
        user_skills=user_skills,
        required_level=3,
    )

    assert [item.skill_name for item in result.matched_skills] == ["Python"]
    assert [item.skill_name for item in result.weak_skills] == ["Redis"]
    assert [item.skill_name for item in result.missing_skills] == ["MySQL"]
    assert result.matched_skills[0].status == JobMatchSkillStatus.MATCHED
    assert result.weak_skills[0].status == JobMatchSkillStatus.WEAK
    assert result.missing_skills[0].status == JobMatchSkillStatus.MISSING
