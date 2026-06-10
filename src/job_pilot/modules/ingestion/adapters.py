from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from job_pilot.modules.job_posts.enums import KnownJobSourcePlatform

"""
这里的 adapters 都不是固定死的，而是要根据“爬虫”数据及时更新的；因为
1. 爬取的网页结构或者数据结构可能发生变化
2. 可能会有新的数据源加入，则新增对应 adapter
"""


@dataclass(slots=True)
class JobDraft:
    """
    adapter 输出的中间结构，之后供 normalization 处理录入，应尽可能保持稳定。

    adapter 只做来源字段到统一草稿字段的映射；
    枚举归一、地点拆分、经验/学历解析等规则放 normalization。
    """

    source_platform: str
    external_job_id: str | None
    source_url: str | None

    title: str
    company_name: str | None
    company_url: str | None

    raw_location_text: str | None
    raw_country_name: str | None
    raw_city_name: str | None

    raw_description: str | None
    raw_experience: str | int | None
    raw_education: str | None
    raw_employment_type: str | None
    raw_flexibility: str | None

    raw_salary: str | None
    raw_skills: list[str]
    published_at_raw: Any


class BaseJobAdapter(ABC):
    """
    负责字段映射
    """

    source_platform: str

    @abstractmethod
    def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
        """把来源 raw payload 映射成 JobDraft。"""


class AlibabaJobAdapter(BaseJobAdapter):
    source_platform = KnownJobSourcePlatform.ALIBABA.value

    def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
        source_url = _first_text(raw_payload, "job_url", "url", "source_url")
        return JobDraft(
            source_platform=self.source_platform,
            external_job_id=_external_id_from_url(source_url, "positionId", "position_id")
            or _first_text(raw_payload, "position_id", "positionId", "job_id", "id"),
            source_url=source_url,
            title=_first_text(raw_payload, "title", "job_name", "name") or "",
            company_name=_first_text(raw_payload, "company_name") or "阿里巴巴",
            company_url=_first_text(raw_payload, "company_url"),
            raw_location_text=_first_text(raw_payload, "area", "location", "work_location"),
            raw_country_name=_first_text(raw_payload, "country", "country_name") or "中国",
            raw_city_name=_first_text(raw_payload, "city", "city_name"),
            raw_description=_join_description_parts(raw_payload, "description", "requirement"),
            raw_experience=raw_payload.get("experience"),
            raw_education=_first_text(raw_payload, "degree", "education"),
            raw_employment_type=_first_text(raw_payload, "job_type", "employment_type"),
            raw_flexibility=_first_text(raw_payload, "flexibility", "workplace_type"),
            raw_salary=_first_text(
                raw_payload,
                "salary",
                "salary_text",
                "salary_range",
                "salary_desc",
                "salary_description",
                "pay",
                "compensation",
                "薪资",
                "薪酬",
            ),
            raw_skills=[],
            published_at_raw=raw_payload.get("publish_time") or raw_payload.get("published_at"),
        )


class TencentJobAdapter(BaseJobAdapter):
    source_platform = KnownJobSourcePlatform.TENCENT.value

    def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
        source_url = _first_text(raw_payload, "job_url", "url", "source_url")
        return JobDraft(
            source_platform=self.source_platform,
            external_job_id=_first_text(raw_payload, "id", "job_id", "position_id"),
            source_url=source_url,
            title=_first_text(raw_payload, "job_name", "title", "name") or "",
            company_name=_first_text(raw_payload, "company_name") or "腾讯",
            company_url=_first_text(raw_payload, "company_url"),
            raw_location_text=_first_text(raw_payload, "city_name", "location", "area"),
            raw_country_name=_first_text(raw_payload, "country_name", "country") or "中国",
            raw_city_name=_first_text(raw_payload, "city_name", "city"),
            raw_description=_join_description_parts(
                raw_payload, "job_desc", "description", "requirement"
            ),
            raw_experience=raw_payload.get("experience"),
            raw_education=_first_text(raw_payload, "degree", "education"),
            raw_employment_type=_first_text(raw_payload, "job_type", "employment_type"),
            raw_flexibility=_first_text(raw_payload, "flexibility", "workplace_type"),
            raw_salary=_first_text(
                raw_payload,
                "salary",
                "salary_text",
                "salary_range",
                "salary_desc",
                "salary_description",
                "pay",
                "compensation",
                "薪资",
                "薪酬",
            ),
            raw_skills=[],
            published_at_raw=raw_payload.get("publish_time") or raw_payload.get("published_at"),
        )


class JaabzJobAdapter(BaseJobAdapter):
    source_platform = KnownJobSourcePlatform.JAABZ.value

    def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
        source_url = _first_text(raw_payload, "job_url", "url", "source_url")
        return JobDraft(
            source_platform=self.source_platform,
            external_job_id=_first_text(raw_payload, "job_id", "id", "position_id"),
            source_url=source_url,
            title=_first_text(raw_payload, "title", "job_name", "name") or "",
            company_name=_first_text(raw_payload, "company_name", "company"),
            company_url=_first_text(raw_payload, "company_url"),
            raw_location_text=_first_text(raw_payload, "area", "location", "work_location"),
            raw_country_name=_first_text(raw_payload, "country", "country_name"),
            raw_city_name=_first_text(raw_payload, "city", "city_name"),
            raw_description=_join_description_parts(
                raw_payload, "details", "description", "job_desc", "requirement"
            ),
            raw_experience=raw_payload.get("experience"),
            raw_education=_first_text(raw_payload, "degree", "education"),
            raw_employment_type=_first_text(raw_payload, "job_type", "employment_type"),
            raw_flexibility=_first_text(raw_payload, "flexibility", "workplace_type"),
            raw_salary=_first_text(
                raw_payload,
                "salary",
                "salary_text",
                "salary_range",
                "salary_desc",
                "salary_description",
                "pay",
                "compensation",
                "薪资",
                "薪酬",
            ),
            raw_skills=[],
            published_at_raw=raw_payload.get("release_time") or raw_payload.get("publish_time"),
        )


ADAPTER_REGISTRY: dict[str, type[BaseJobAdapter]] = {
    KnownJobSourcePlatform.ALIBABA.value: AlibabaJobAdapter,
    KnownJobSourcePlatform.TENCENT.value: TencentJobAdapter,
    KnownJobSourcePlatform.JAABZ.value: JaabzJobAdapter,
}


def get_job_adapter(source_platform: str) -> BaseJobAdapter:
    adapter_cls = ADAPTER_REGISTRY[source_platform]
    return adapter_cls()


def _first_text(raw_payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        text_value = _clean_text(raw_payload.get(key))
        if text_value is not None:
            return text_value
    return None


def _skill_texts_from_value(value: object | None) -> list[str]:
    """解析 adapter 已明确映射的技能字段值，供后续真实来源字段接入复用。"""

    if value is None:
        return []
    if isinstance(value, str):
        text_value = _clean_text(value)
        return [text_value] if text_value is not None else []
    if isinstance(value, dict):
        return _skill_texts_from_mapping(value)
    if isinstance(value, list | tuple | set):
        skill_texts: list[str] = []
        for item in value:
            skill_texts.extend(_skill_texts_from_value(item))
        return skill_texts

    text_value = _clean_text(value)
    return [text_value] if text_value is not None else []


def _skill_texts_from_mapping(value: dict[object, object]) -> list[str]:
    for key in ("name", "label", "text", "skill", "title", "value"):
        item = value.get(key)
        text_value = _clean_text(item)
        if text_value is not None:
            return [text_value]
    return []


def _clean_text(value: object | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).replace("\u3000", " ").replace("\xa0", " ").strip()
    if not text_value or text_value.casefold() in {"none", "null", "nan", "n/a", "na", "-", "--"}:
        return None
    return " ".join(text_value.split())


def _join_description_parts(raw_payload: dict[str, Any], *keys: str) -> str | None:
    parts = [_clean_text(raw_payload.get(key)) for key in keys]
    normalized_parts = [part for part in parts if part is not None]
    return "\n\n".join(normalized_parts) if normalized_parts else None


def _external_id_from_url(source_url: str | None, *query_keys: str) -> str | None:
    if not source_url:
        return None
    query = parse_qs(urlparse(source_url).query)
    for key in query_keys:
        values = query.get(key)
        if not values:
            continue
        value = _clean_text(values[0])
        if value is not None:
            return value
    return None
