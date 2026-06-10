# ruff: noqa: E501
from __future__ import annotations

import re

from job_pilot.modules.job_posts.enums import SalaryPeriod

from .text import clean_text
from .types import NormalizedSalary

_NEGOTIABLE_KEYWORDS = ("面议", "negotiable", "薪资不限", "薪资面议", "面谈")
_CHINESE_SALARY_CONTEXT_KEYWORDS = (
    "薪资",
    "薪酬",
    "待遇",
    "工资",
    "月薪",
    "年薪",
)
# 尽量只截取像薪资的片段，避免把经验年限、日期误识别成薪资。
_SALARY_SEGMENT_PATTERNS = [
    re.compile(
        r"(?:usd|sgd|nzd|eur|gbp|\$|s\$|€|£)\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|w|万|千)?\s*[-~—–至到]\s*(?:usd|sgd|nzd|eur|gbp|\$|s\$|€|£)?\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|w|万|千)?\s*(?:/\s*(?:year|yr|month|day|hour|h))?",
        re.I,
    ),
    re.compile(
        r"(?:rmb|cny|人民币|￥|¥)?\s*\d+(?:\.\d+)?\s*(?:k|w|万|千|元)?\s*[-~—–至到]\s*(?:rmb|cny|人民币|￥|¥)?\s*\d+(?:\.\d+)?\s*(?:k|w|万|千|元)?\s*(?:/\s*(?:月|天|日|年|hour|hr|h|day|year|month|yr))?(?:\s*[·x×]\s*\d+\s*薪)?",
        re.I,
    ),
    re.compile(r"\d+(?:\.\d+)?\s*(?:k|w|万|千)\s*(?:以上|起|\+)?", re.I),
]
_NUMBER_PATTERN = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_CURRENCY_PATTERN = re.compile(r"(?:usd|sgd|nzd|eur|gbp|rmb|cny|人民币|\$|s\$|€|£|￥|¥)", re.I)
_SALARY_UNIT_PATTERN = re.compile(
    r"(?:k\b|w\b|万|千|元|/月|/天|/日|/年|/hour|/hr|/h|/day|/year|/month|/yr|薪)",
    re.I,
)
_ENGLISH_SALARY_CONTEXT_PATTERN = re.compile(r"\b(?:salary|compensation|pay)\b", re.I)
_NEGOTIABLE_SEGMENT_PATTERNS = [
    re.compile(
        r"(?:薪资|薪酬|待遇|工资|月薪|年薪)\s*[:：]?\s*(?:面议|薪资不限|薪资面议|面谈)",
        re.I,
    ),
    re.compile(
        r"(?:salary|compensation|pay)\s*[:：]?\s*(?:is\s*)?(?:negotiable|tbd|to\s+be\s+discussed)",
        re.I,
    ),
    re.compile(
        r"(?:negotiable|tbd|to\s+be\s+discussed)\s+(?:salary|compensation|pay)",
        re.I,
    ),
]


def normalize_salary(raw_salary: object | None) -> NormalizedSalary:
    """解析常见薪资文本。

    只结构化明确的 text/min/max/currency/period。
    只处理 adapter 显式映射出的薪资字段，不从岗位标题或描述中兜底提取。
    支持：10-15K、20-30k·14薪、150-200/天、1.5-2万/月、100-150K/year、USD 80k-120k。
    """

    salary_text = _pick_salary_text(raw_salary)
    if salary_text is None:
        return NormalizedSalary(None, None, None, "CNY", SalaryPeriod.UNKNOWN)

    normalized_text = salary_text.casefold().replace(" ", "")
    currency = _normalize_currency(normalized_text)
    period = _normalize_salary_period(normalized_text)
    if any(keyword in normalized_text for keyword in _NEGOTIABLE_KEYWORDS):
        return NormalizedSalary(salary_text, None, None, currency, period)

    numbers = [_parse_number(number) for number in _NUMBER_PATTERN.findall(normalized_text)]
    numbers = [number for number in numbers if number is not None]
    if not numbers:
        return NormalizedSalary(salary_text, None, None, currency, period)

    multiplier = _salary_multiplier(normalized_text)
    salary_min = int(numbers[0] * multiplier)
    salary_max = int(numbers[1] * multiplier) if len(numbers) > 1 else salary_min
    if salary_min > salary_max:
        salary_min, salary_max = salary_max, salary_min

    return NormalizedSalary(
        salary_text=salary_text,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        salary_period=period,
    )


def _pick_salary_text(raw_salary: object | None) -> str | None:
    text = clean_text(raw_salary)
    if text is None:
        return None

    segment = _extract_salary_segment(text)
    if segment is not None:
        return segment

    negotiable_segment = _extract_negotiable_segment(text)
    if negotiable_segment is not None:
        return negotiable_segment
    return None


def _extract_salary_segment(text: str) -> str | None:
    for pattern in _SALARY_SEGMENT_PATTERNS:
        for match in pattern.finditer(text):
            segment = match.group(0).strip()
            if _looks_like_salary_segment(segment, text, match.start(), match.end()):
                return segment
    return None


def _extract_negotiable_segment(text: str) -> str | None:
    normalized_text = text.casefold()
    if len(text) <= 120 and any(keyword in normalized_text for keyword in _NEGOTIABLE_KEYWORDS):
        return text

    for pattern in _NEGOTIABLE_SEGMENT_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match.group(0).strip()
    return None


def _looks_like_salary_segment(segment: str, source_text: str, start: int, end: int) -> bool:
    """判断数字片段是否足够像薪资，减少描述兜底带来的误判。"""

    if _CURRENCY_PATTERN.search(segment) is not None:
        return True
    if _SALARY_UNIT_PATTERN.search(segment) is not None:
        return True

    context_start = max(0, start - 24)
    context_end = min(len(source_text), end + 24)
    context = source_text[context_start:context_end].casefold()
    return any(keyword in context for keyword in _CHINESE_SALARY_CONTEXT_KEYWORDS) or (
        _ENGLISH_SALARY_CONTEXT_PATTERN.search(context) is not None
    )


def _parse_number(value: str) -> float | None:
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _salary_multiplier(normalized_text: str) -> int:
    if "万" in normalized_text or re.search(r"\d(?:\.\d+)?w\b", normalized_text):
        return 10_000
    if "k" in normalized_text or "千" in normalized_text:
        return 1_000
    return 1


def _normalize_currency(normalized_text: str) -> str:
    if "sgd" in normalized_text or "s$" in normalized_text:
        return "SGD"
    if "nzd" in normalized_text:
        return "NZD"
    if "eur" in normalized_text or "€" in normalized_text:
        return "EUR"
    if "gbp" in normalized_text or "£" in normalized_text:
        return "GBP"
    if "usd" in normalized_text or "$" in normalized_text:
        return "USD"
    return "CNY"


def _normalize_salary_period(normalized_text: str) -> SalaryPeriod:
    if re.search(r"/(?:hour|hr|h)\b", normalized_text):
        return SalaryPeriod.HOUR
    if (
        "/天" in normalized_text
        or "/日" in normalized_text
        or re.search(r"/day\b", normalized_text)
    ):
        return SalaryPeriod.DAY
    if "/月" in normalized_text or re.search(r"/month\b", normalized_text):
        return SalaryPeriod.MONTH
    if "/年" in normalized_text or re.search(r"/(?:year|yr)\b", normalized_text):
        return SalaryPeriod.YEAR
    if "月薪" in normalized_text:
        return SalaryPeriod.MONTH
    if "年薪" in normalized_text:
        return SalaryPeriod.YEAR
    return SalaryPeriod.UNKNOWN
