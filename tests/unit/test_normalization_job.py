from __future__ import annotations

from job_pilot.modules.ingestion.adapters import JobDraft
from job_pilot.modules.ingestion.normalization import normalize_job_draft
from job_pilot.modules.job_posts.enums import (
    EducationLevel,
    ExperienceLevel,
    SalaryPeriod,
    WorkplaceType,
)


def test_normalize_job_draft_splits_core_job_fields() -> None:
    """岗位草稿规范化会拆分核心岗位字段。"""

    draft = JobDraft(
        source_platform="alibaba",
        external_job_id="ali-001",
        source_url="https://jobs.example.com/ali-001",
        title="  后端开发工程师  ",
        company_name="阿里巴巴",
        company_url=None,
        raw_location_text="北京/上海/远程",
        raw_country_name="中国",
        raw_city_name=None,
        raw_description="负责 FastAPI 服务建设，提供签证支持和 relocation support。",
        raw_experience="3-5年",
        raw_education="本科",
        raw_employment_type="全职",
        raw_flexibility="混合办公",
        raw_salary="15-30K",
        raw_skills=[],
        published_at_raw="2026-06-01",
    )

    normalized = normalize_job_draft(draft)

    assert normalized.title == "后端开发工程师"
    assert normalized.salary_text == "15-30K"
    assert normalized.salary_min == 15000
    assert normalized.salary_max == 30000
    assert normalized.salary_period == SalaryPeriod.UNKNOWN
    assert normalized.experience_level == ExperienceLevel.MID
    assert normalized.experience_min_years == 3
    assert normalized.experience_max_years == 5
    assert normalized.education_level == EducationLevel.BACHELOR
    assert normalized.workplace_type == WorkplaceType.REMOTE
    assert normalized.locations == "北京 / 上海 / 远程 / 中国"
    assert normalized.is_remote is True
    assert normalized.has_visa_sponsorship is True
    assert normalized.has_relocation_support is True


def test_normalize_job_draft_does_not_extract_salary_from_description() -> None:
    """规范化不会从岗位描述里误提取薪资。"""

    draft = JobDraft(
        source_platform="jaabz",
        external_job_id="jb-001",
        source_url="https://jobs.example.com/jb-001",
        title="Backend Engineer",
        company_name="Remote Tech",
        company_url=None,
        raw_location_text="Remote",
        raw_country_name=None,
        raw_city_name=None,
        raw_description="岗位描述：薪资 1.5-2万/月，要求 3-5 年经验。",
        raw_experience="3-5 years",
        raw_education=None,
        raw_employment_type="full-time",
        raw_flexibility="remote",
        raw_salary=None,
        raw_skills=[],
        published_at_raw="2026-06-01",
    )

    normalized = normalize_job_draft(draft)

    assert normalized.salary_text is None
    assert normalized.salary_min is None
    assert normalized.salary_max is None
    assert normalized.salary_period == SalaryPeriod.UNKNOWN
