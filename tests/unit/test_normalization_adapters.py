from __future__ import annotations

from job_pilot.modules.ingestion.adapters import TaotianJobAdapter, TencentJobAdapter


def test_job_adapters_only_map_confirmed_job_fields() -> None:
    """adapter 只映射岗位草稿字段，不猜测技能或公司字段。"""

    raw_payload = {
        "title": "Backend Engineer",
        "job_name": "Backend Engineer",
        "area": "北京",
        "city_name": "深圳",
        "description": "负责服务端开发",
        "requirement": "本科，三年以上经验",
        "experience": "3年以上",
        "degree": "本科",
        "salary": "20-30K",
        "publish_time": "2026-08-01",
        "skills": ["Python", "FastAPI"],
        "company_name": "不应进入草稿",
    }

    taotian_draft = TaotianJobAdapter().to_draft(raw_payload)
    tencent_draft = TencentJobAdapter().to_draft(raw_payload)

    assert taotian_draft.title == "Backend Engineer"
    assert taotian_draft.raw_location == "北京"
    assert taotian_draft.raw_description == "负责服务端开发\n\n本科，三年以上经验"
    assert taotian_draft.raw_experience == "3年以上"
    assert taotian_draft.raw_education == "本科"
    assert taotian_draft.raw_salary == "20-30K"
    assert tencent_draft.raw_location == "深圳"
    assert set(taotian_draft.__dataclass_fields__) == {
        "title",
        "raw_location",
        "raw_description",
        "raw_experience",
        "raw_education",
        "raw_salary",
        "published_at_raw",
    }
