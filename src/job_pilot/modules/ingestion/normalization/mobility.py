from __future__ import annotations

from .types import NormalizedMobility

_VISA_POSITIVE_KEYWORDS = (
    "签证支持",
    "提供签证",
    "支持工签",
    "visa sponsorship",
    "sponsor visa",
    "work visa sponsorship",
)
_VISA_NEGATIVE_KEYWORDS = (
    "不提供签证",
    "不支持签证",
    "无签证支持",
    "不能提供签证",
    "no visa sponsorship",
    "does not sponsor",
    "do not sponsor",
    "cannot sponsor",
    "unable to sponsor",
    "must be authorized to work",
)
_RELOCATION_POSITIVE_KEYWORDS = (
    "搬迁支持",
    "提供搬迁",
    "relocation support",
    "relocation package",
)
_RELOCATION_NEGATIVE_KEYWORDS = (
    "不提供搬迁",
    "不支持搬迁",
    "无搬迁支持",
    "no relocation",
    "relocation is not provided",
    "relocation not provided",
)


def normalize_mobility(description: str | None) -> NormalizedMobility:
    """从详情文本中提取签证、搬迁等海外岗位扩展信息。"""

    if description is None:
        return NormalizedMobility(None, None, None)

    lowered_text = description.casefold()
    has_visa_sponsorship = _detect_tri_state(
        lowered_text,
        positive_keywords=_VISA_POSITIVE_KEYWORDS,
        negative_keywords=_VISA_NEGATIVE_KEYWORDS,
    )
    has_relocation_support = _detect_tri_state(
        lowered_text,
        positive_keywords=_RELOCATION_POSITIVE_KEYWORDS,
        negative_keywords=_RELOCATION_NEGATIVE_KEYWORDS,
    )
    note_parts: list[str] = []
    if has_visa_sponsorship is True:
        note_parts.append("包含签证支持说明")
    elif has_visa_sponsorship is False:
        note_parts.append("包含不支持签证说明")
    if has_relocation_support is True:
        note_parts.append("包含搬迁支持说明")
    elif has_relocation_support is False:
        note_parts.append("包含不支持搬迁说明")

    return NormalizedMobility(
        has_visa_sponsorship=has_visa_sponsorship,
        has_relocation_support=has_relocation_support,
        work_authorization_note="；".join(note_parts) if note_parts else None,
    )


def _detect_tri_state(
    text: str,
    *,
    positive_keywords: tuple[str, ...],
    negative_keywords: tuple[str, ...],
) -> bool | None:
    """按明确否定优先识别三态字段。"""

    if any(keyword in text for keyword in negative_keywords):
        return False
    if any(keyword in text for keyword in positive_keywords):
        return True
    return None
