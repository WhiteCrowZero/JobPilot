from __future__ import annotations

import re

from .text import clean_text
from .types import NormalizedLocation

_LOCATION_SPLIT_PATTERN = re.compile(r"[,，;；、|/]+")
_REMOTE_KEYWORDS = ("远程", "remote", "work from home", "wfh", "居家办公")


def normalize_location(
    *,
    raw_location_text: object | None,
    raw_country_name: object | None,
    raw_city_name: object | None,
    raw_flexibility: object | None,
) -> NormalizedLocation:
    """把来源地点压缩为 MVP 可用的 locations 文本和 is_remote。

    目前不拆国家、城市、区域，也不做地理编码。原因是不同来源地点表达差异大，
    自动清洗不稳定；先保留原始可读文本，提供轻量 location ILIKE 查询。
    """

    parts: list[str] = []
    for value in (raw_location_text, raw_city_name, raw_country_name):
        for part in _split_location_text(value):
            if part not in parts:
                parts.append(part)

    flexibility = clean_text(raw_flexibility)
    combined_text = " ".join([*parts, flexibility or ""]).casefold()
    return NormalizedLocation(
        locations=" / ".join(parts) if parts else None,
        is_remote=any(keyword in combined_text for keyword in _REMOTE_KEYWORDS),
    )


def _split_location_text(value: object | None) -> list[str]:
    location_text = clean_text(value)
    if location_text is None:
        return []
    return [
        part
        for part in (clean_text(part) for part in _LOCATION_SPLIT_PATTERN.split(location_text))
        if part is not None
    ]
