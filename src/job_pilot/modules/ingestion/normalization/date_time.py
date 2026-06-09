from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from .text import clean_text

_EXCEL_EPOCH = datetime(1899, 12, 30, tzinfo=UTC)
_EXCEL_SERIAL_MIN = 20_000  # 1954 左右，足够覆盖现代招聘数据。
_EXCEL_SERIAL_MAX = 80_000  # 2119 左右，避免误把毫秒/秒级时间戳当 Excel 日期。
_UNIX_SECONDS_MIN = 946_684_800  # 2000-01-01


def normalize_published_at(raw_published_at: object | None) -> datetime | None:
    """把来源发布时间解析为 UTC datetime。

    兼容：
    - datetime/date 对象；
    - Excel 日期序列值，例如 45675；
    - Unix 秒/毫秒时间戳；
    - 常见字符串日期：2025-01-18、2025/01/18、2025年01月18日。
    """

    if raw_published_at is None:
        return None
    if isinstance(raw_published_at, datetime):
        return raw_published_at if raw_published_at.tzinfo else raw_published_at.replace(tzinfo=UTC)
    if isinstance(raw_published_at, date):
        return datetime.combine(raw_published_at, time.min, tzinfo=UTC)
    if isinstance(raw_published_at, int | float):
        return _normalize_numeric_datetime(float(raw_published_at))

    published_text = clean_text(raw_published_at)
    if published_text is None:
        return None

    numeric_datetime = _try_parse_numeric_text(published_text)
    if numeric_datetime is not None:
        return numeric_datetime

    normalized_text = (
        published_text.strip()
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
        .replace("Z", "+00:00")
    )

    try:
        parsed_datetime = datetime.fromisoformat(normalized_text)
        return parsed_datetime if parsed_datetime.tzinfo else parsed_datetime.replace(tzinfo=UTC)
    except ValueError:
        pass

    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(normalized_text, date_format).replace(tzinfo=UTC)
        except ValueError:
            continue

    return None


def _try_parse_numeric_text(text: str) -> datetime | None:
    try:
        return _normalize_numeric_datetime(float(text))
    except ValueError:
        return None


def _normalize_numeric_datetime(value: float) -> datetime | None:
    if value <= 0:
        return None
    if _EXCEL_SERIAL_MIN <= value <= _EXCEL_SERIAL_MAX:
        return _EXCEL_EPOCH + timedelta(days=value)
    if value >= _UNIX_SECONDS_MIN * 1000:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    if value >= _UNIX_SECONDS_MIN:
        return datetime.fromtimestamp(value, tz=UTC)
    return None
