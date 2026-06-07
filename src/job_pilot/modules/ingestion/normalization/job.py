from __future__ import annotations

from job_pilot.modules.ingestion.adapters import JobDraft
from job_pilot.modules.job_posts.enums import WorkplaceType

from .date_time import normalize_published_at
from .education import normalize_education_level
from .employment import normalize_employment_type
from .experience import normalize_experience
from .fingerprint import build_job_fingerprint
from .location import normalize_location
from .mobility import normalize_mobility
from .salary import normalize_salary
from .text import clean_long_text, clean_required_text, clean_text
from .types import NormalizedJob
from .workplace import normalize_workplace_type

"""
这里的 normalize 也不是固定死的，而是要根据“后端”数据及时更新的；因为
后端业务字段可能发生变化
"""


def normalize_job_draft(draft: JobDraft) -> NormalizedJob:
    """把来源草稿统一清洗成 normalized tables 可写入的数据。"""

    title = clean_required_text(draft.title, field_name="title")
    company_name = clean_text(draft.company_name)
    company_url = clean_text(draft.company_url)
    source_url = clean_text(draft.source_url)
    description = clean_long_text(draft.raw_description)

    salary = normalize_salary(draft.raw_salary)
    experience = normalize_experience(draft.raw_experience)
    education_level = normalize_education_level(draft.raw_education)
    employment_type = normalize_employment_type(draft.raw_employment_type)
    workplace_type = normalize_workplace_type(
        raw_flexibility=draft.raw_flexibility,
        raw_location_text=draft.raw_location_text,
    )
    location = normalize_location(
        raw_location_text=draft.raw_location_text,
        raw_country_name=draft.raw_country_name,
        raw_city_name=draft.raw_city_name,
        raw_flexibility=draft.raw_flexibility,
    )
    if workplace_type == WorkplaceType.UNKNOWN and location.is_remote:
        workplace_type = WorkplaceType.REMOTE

    mobility = normalize_mobility(description)
    published_at = normalize_published_at(draft.published_at_raw)
    fingerprint = build_job_fingerprint(
        source_platform=draft.source_platform,
        external_job_id=draft.external_job_id,
        source_url=source_url,
        title=title,
        company_name=company_name,
        locations=location.locations,
    )

    return NormalizedJob(
        fingerprint=fingerprint,
        title=title,
        company_name=company_name,
        company_url=company_url,
        source_url=source_url,
        description=description,
        locations=location.locations,
        is_remote=location.is_remote,
        employment_type=employment_type,
        workplace_type=workplace_type,
        experience_level=experience.experience_level,
        experience_min_years=experience.experience_min_years,
        experience_max_years=experience.experience_max_years,
        education_level=education_level,
        salary_text=salary.salary_text,
        salary_min=salary.salary_min,
        salary_max=salary.salary_max,
        salary_currency=salary.salary_currency,
        published_at=published_at,
        has_visa_sponsorship=mobility.has_visa_sponsorship,
        has_relocation_support=mobility.has_relocation_support,
        work_authorization_note=mobility.work_authorization_note,
    )
