from __future__ import annotations

from job_pilot.modules.ingestion.adapters import JobDraft

from .date_time import normalize_published_at
from .education import normalize_education_level
from .fingerprint import build_job_fingerprint
from .text import clean_long_text, clean_required_text, clean_text
from .types import NormalizedJob

"""
这里的 normalize 也不是固定死的，而是要根据“后端”数据及时更新的；因为
后端业务字段可能发生变化
"""


def normalize_job_draft(
    draft: JobDraft,
    *,
    source_platform: str,
    external_job_id: str | None,
    source_url: str | None,
) -> NormalizedJob:
    """把来源草稿统一清洗成 normalized tables 可写入的数据。"""

    title = clean_required_text(draft.title, field_name="title")
    normalized_source_url = clean_text(source_url)
    description = clean_long_text(draft.raw_description)
    locations = clean_text(draft.raw_location)
    experience_text = clean_text(draft.raw_experience)
    salary_text = clean_text(draft.raw_salary)
    education_level = normalize_education_level(draft.raw_education)
    published_at = normalize_published_at(draft.published_at_raw)
    fingerprint = build_job_fingerprint(
        source_platform=source_platform,
        external_job_id=external_job_id,
        source_url=normalized_source_url,
        title=title,
        locations=locations,
    )

    return NormalizedJob(
        fingerprint=fingerprint,
        title=title,
        source_url=normalized_source_url,
        description=description,
        locations=locations,
        experience_text=experience_text,
        education_level=education_level,
        salary_text=salary_text,
        published_at=published_at,
    )
