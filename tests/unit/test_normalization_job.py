from __future__ import annotations

from datetime import UTC, datetime

from job_pilot.modules.ingestion.adapters import JobDraft
from job_pilot.modules.ingestion.normalization import normalize_job_draft
from job_pilot.modules.job_posts.enums import EducationLevel


def test_normalize_job_draft_cleans_confirmed_job_fields() -> None:
    """岗位草稿规范化只生成已确认的岗位字段。"""

    draft = JobDraft(
        title="  后端开发工程师  ",
        raw_location="  北京 / 上海  ",
        raw_description="  负责 FastAPI 服务建设。  ",
        raw_experience="  3-5年  ",
        raw_education="本科",
        raw_salary="  15-30K  ",
        published_at_raw="2026-06-01",
    )

    normalized = normalize_job_draft(
        draft,
        source_platform="taotian",
        external_job_id="ali-001",
        source_url=" https://jobs.example.com/ali-001 ",
    )

    assert normalized.title == "后端开发工程师"
    assert normalized.locations == "北京 / 上海"
    assert normalized.description == "负责 FastAPI 服务建设。"
    assert normalized.experience_text == "3-5年"
    assert normalized.education_level == EducationLevel.BACHELOR
    assert normalized.salary_text == "15-30K"
    assert normalized.source_url == "https://jobs.example.com/ali-001"
    assert normalized.published_at == datetime(2026, 6, 1, tzinfo=UTC)


def test_normalize_job_draft_does_not_infer_salary_from_description() -> None:
    """薪资只保留来源明确映射的文本，不从正文猜测。"""

    normalized = normalize_job_draft(
        JobDraft(
            title="Backend Engineer",
            raw_location=None,
            raw_description="岗位描述：薪资 1.5-2万/月。",
            raw_experience=None,
            raw_education=None,
            raw_salary=None,
            published_at_raw=None,
        ),
        source_platform="tencent",
        external_job_id="tx-001",
        source_url=None,
    )

    assert normalized.salary_text is None
    assert normalized.description == "岗位描述：薪资 1.5-2万/月。"
    assert normalized.education_level == EducationLevel.UNKNOWN
