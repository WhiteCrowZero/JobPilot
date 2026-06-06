from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

from job_pilot.core.exceptions import ValidationError

_MULTI_SPACE_PATTERN = re.compile(r"[ \t\f\v]+")
_BLANK_LIKE_VALUES = {"", "none", "null", "nan", "n/a", "na", "-", "--", "无", "不限", "暂无"}


def clean_text(value: object | None) -> str | None:
    """把来源字段清洗为短文本；空值、NaN、占位符统一转 None。"""

    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, Decimal) and value.is_nan():
        return None

    text = str(value).replace("\u3000", " ").replace("\xa0", " ")
    text = _MULTI_SPACE_PATTERN.sub(" ", text).strip()
    if text.casefold() in _BLANK_LIKE_VALUES:
        return None
    return text or None


def clean_required_text(value: object | None, *, field_name: str) -> str:
    cleaned_value = clean_text(value)
    if cleaned_value is None:
        raise ValidationError(
            f"Job draft {field_name} is required", code="JOB_DRAFT_FIELD_REQUIRED"
        )
    return cleaned_value


def clean_long_text(value: object | None) -> str | None:
    """清洗岗位详情文本：保留换行结构，但压缩多余空白和连续空行。"""

    raw_text = clean_text(value)
    if raw_text is None:
        return None

    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized_lines: list[str] = []
    previous_blank = False
    for line in lines:
        cleaned_line = _MULTI_SPACE_PATTERN.sub(" ", line).strip()
        if cleaned_line:
            normalized_lines.append(cleaned_line)
            previous_blank = False
            continue
        if not previous_blank:
            normalized_lines.append("")
            previous_blank = True

    cleaned_value = "\n".join(normalized_lines).strip()
    return cleaned_value or None


def first_text(raw_payload: dict[str, Any], *keys: str) -> str | None:
    """按优先级从 raw payload 取第一个非空文本。"""

    for key in keys:
        value = raw_payload.get(key)
        text_value = clean_text(value)
        if text_value is not None:
            return text_value
    return None
