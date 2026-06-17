from __future__ import annotations

from job_pilot.modules.ingestion.adapters import (
    AlibabaJobAdapter,
    JaabzJobAdapter,
    TencentJobAdapter,
)


def test_job_adapters_do_not_guess_skill_like_fields_without_explicit_mapping() -> None:
    """adapter 只映射已确认的来源字段，不从通用字段名猜测技能。"""

    raw_payload = {
        "job_id": "source-001",
        "id": "source-001",
        "position_id": "source-001",
        "job_url": "https://jobs.example.com/source-001",
        "title": "Backend Engineer",
        "job_name": "Backend Engineer",
        "area": "北京",
        "city_name": "北京",
        "skills": ["Python", "FastAPI"],
        "tags": ["Redis"],
        "keywords": "Docker, Kubernetes",
        "技术栈": "FastAPI / PostgreSQL",
        "技能": "Python",
    }

    drafts = [
        AlibabaJobAdapter().to_draft(raw_payload),
        TencentJobAdapter().to_draft(raw_payload),
        JaabzJobAdapter().to_draft(raw_payload),
    ]

    assert [draft.raw_skills for draft in drafts] == [[], [], []]
