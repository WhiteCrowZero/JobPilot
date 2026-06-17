from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable

from job_pilot.modules.job_skills.skill_sync_contracts import RawSkillCandidate

_SPLIT_PATTERN = re.compile(r"[\n\r,，、;/；|]+")
_ALLOWED_CHARS_PATTERN = re.compile(r"[^0-9a-z\u4e00-\u9fff+#.]+")


def extract_raw_skill_candidates(raw_skills: list[str]) -> list[RawSkillCandidate]:
    """从 adapter 已提取出的原始技能文本中拆分技能候选。"""

    texts: list[str] = []
    for value in raw_skills:
        texts.extend(_split_raw_skill_text(value))
    return [RawSkillCandidate(text=text) for text in texts]


def build_skill_content_hash(candidates: Iterable[RawSkillCandidate]) -> str | None:
    """根据 raw skill candidates 计算稳定 hash，用于判断岗位技能是否需要更新。"""

    normalized_items = sorted(
        {
            normalize_skill_alias(candidate.text)
            for candidate in candidates
            if normalize_skill_alias(candidate.text)
        }
    )
    if not normalized_items:
        return None
    raw = json.dumps(normalized_items, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_skill_alias(value: str) -> str:
    """把技能名或别名归一成用于匹配的 key。"""

    text = _clean_skill_text(value)
    if text is None:
        return ""
    normalized = text.casefold()
    normalized = normalized.replace("＋", "+").replace("＃", "#")
    normalized = _ALLOWED_CHARS_PATTERN.sub("", normalized)
    return normalized


def _clean_skill_text(value: object | None) -> str | None:
    """清洗单个 raw skill 文本，但不负责归一到标准技能。"""

    if value is None:
        return None
    text = str(value).replace("\u3000", " ").replace("\xa0", " ").strip()
    if not text or text.casefold() in {"none", "null", "nan", "n/a", "na", "-", "--"}:
        return None
    return " ".join(text.split())


def _split_raw_skill_text(value: object | None) -> list[str]:
    """把 adapter 交出的原始技能文本拆成技能候选列表。"""

    if value is None:
        return []
    if isinstance(value, str):
        parts = _SPLIT_PATTERN.split(value)
        return _deduplicate_cleaned(parts)
    if isinstance(value, Iterable):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.extend(_SPLIT_PATTERN.split(item))
            elif isinstance(item, dict):
                parts.extend(_extract_skill_texts_from_mapping(item))
            elif item is not None:
                parts.append(str(item))
        return _deduplicate_cleaned(parts)
    return _deduplicate_cleaned([str(value)])


def _deduplicate_cleaned(values: Iterable[object | None]) -> list[str]:
    cleaned_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_skill_text(value)
        if text is None:
            continue
        normalized = normalize_skill_alias(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned_values.append(text)
    return cleaned_values


def _extract_skill_texts_from_mapping(value: dict[object, object]) -> list[str]:
    for key in ("name", "label", "text", "skill", "title", "value"):
        item = value.get(key)
        text = _clean_skill_text(item)
        if text is not None:
            return [text]
    return []
