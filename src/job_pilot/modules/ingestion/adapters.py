from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any

from job_pilot.modules.job_posts.enums import KnownJobSourcePlatform

"""
这里的 adapters 都不是固定死的，而是要根据“爬虫”数据及时更新的；因为
1. 爬取的网页结构或者数据结构可能发生变化
2. 可能会有新的数据源加入，则新增对应 adapter
"""


@dataclass(slots=True, frozen=True)
class JobDraft:
    """
    adapter 输出的中间结构，之后供 normalization 处理录入，应尽可能保持稳定。
    adapter 只做来源字段到统一草稿字段的映射，字段解析等规则放 normalization。
    """

    title: str
    raw_location: str | None
    raw_description: str | None
    raw_experience: str | int | None
    raw_education: str | None
    raw_salary: str | None
    published_at_raw: str | date | None


class BaseJobAdapter(ABC):
    """
    负责字段映射
    """

    source_platform: str

    @abstractmethod
    def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
        """把来源 raw payload 映射成 JobDraft。"""


class TaotianJobAdapter(BaseJobAdapter):
    source_platform = KnownJobSourcePlatform.TAOTIAN.value

    def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
        return JobDraft(
            title=_first_text(raw_payload, "title", "job_name", "name") or "",
            raw_location=_first_text(raw_payload, "area", "location", "work_location"),
            raw_description=_join_description_parts(raw_payload, "description", "requirement"),
            raw_experience=_first_text(raw_payload, "experience"),
            raw_education=_first_text(raw_payload, "degree", "education"),
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
            published_at_raw=_first_text(raw_payload, "publish_time", "published_at"),
        )


class TencentJobAdapter(BaseJobAdapter):
    source_platform = KnownJobSourcePlatform.TENCENT.value

    def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
        return JobDraft(
            title=_first_text(raw_payload, "job_name", "title", "name") or "",
            raw_location=_first_text(raw_payload, "city_name", "location", "area"),
            raw_description=_join_description_parts(
                raw_payload, "job_desc", "description", "requirement"
            ),
            raw_experience=_first_text(raw_payload, "experience"),
            raw_education=_first_text(raw_payload, "degree", "education"),
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
            published_at_raw=_first_text(raw_payload, "publish_time", "published_at"),
        )


class MockJobAdapter(BaseJobAdapter):
    """模拟生产者的显式字段 adapter。"""

    source_platform = KnownJobSourcePlatform.MOCK.value

    def to_draft(self, raw_payload: dict[str, Any]) -> JobDraft:
        return JobDraft(
            title=_first_text(raw_payload, "title") or "",
            raw_location=_first_text(raw_payload, "location"),
            raw_description=_first_text(raw_payload, "description"),
            raw_experience=_first_text(raw_payload, "experience"),
            raw_education=_first_text(raw_payload, "education"),
            raw_salary=_first_text(raw_payload, "salary"),
            published_at_raw=_first_text(raw_payload, "published_at"),
        )


ADAPTER_REGISTRY: dict[str, type[BaseJobAdapter]] = {
    KnownJobSourcePlatform.TAOTIAN.value: TaotianJobAdapter,
    KnownJobSourcePlatform.TENCENT.value: TencentJobAdapter,
    KnownJobSourcePlatform.MOCK.value: MockJobAdapter,
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
