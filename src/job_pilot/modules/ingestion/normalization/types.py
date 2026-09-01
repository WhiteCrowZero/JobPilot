from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from job_pilot.modules.job_posts.enums import EducationLevel


@dataclass(slots=True, frozen=True)
class NormalizedJob:
    """岗位草稿清洗后的统一结构，供 ingestion service 落库使用。"""

    fingerprint: str
    title: str
    source_url: str | None
    description: str | None
    locations: str | None
    experience_text: str | None
    education_level: EducationLevel
    salary_text: str | None
    published_at: datetime | None
