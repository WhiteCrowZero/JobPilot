from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

MIN_BUSINESS_DATE = date(2000, 1, 1)
MAX_FUTURE_DAYS = 3650


def max_business_date() -> date:
    """返回对外输入日期允许的最远未来日期。"""

    return date.today() + timedelta(days=MAX_FUTURE_DAYS)


def validate_business_date(value: date | None, *, field_name: str) -> date | None:
    """校验业务日期不越过项目允许的历史和未来边界。"""

    if value is None:
        return None
    max_date = max_business_date()
    if value < MIN_BUSINESS_DATE or value > max_date:
        raise ValueError(f"{field_name} must be between {MIN_BUSINESS_DATE} and {max_date}")
    return value


def validate_past_or_today_date(value: date | None, *, field_name: str) -> date | None:
    """校验只允许历史或当天的业务日期。"""

    validate_business_date(value, field_name=field_name)
    if value is not None and value > date.today():
        raise ValueError(f"{field_name} must not be in the future")
    return value


def validate_business_datetime(
    value: datetime | None,
    *,
    field_name: str,
) -> datetime | None:
    """校验业务时间不越过项目允许的日期边界。"""

    if value is None:
        return None
    value_date = value.astimezone(UTC).date() if value.tzinfo is not None else value.date()
    validate_business_date(value_date, field_name=field_name)
    return value


def validate_date_order(
    start: date | None,
    end: date | None,
    *,
    start_name: str,
    end_name: str,
) -> None:
    """校验开始日期不能晚于结束日期。"""

    if start is not None and end is not None and start > end:
        raise ValueError(f"{start_name} must be <= {end_name}")


def validate_datetime_order(
    start: datetime | None,
    end: datetime | None,
    *,
    start_name: str,
    end_name: str,
) -> None:
    """校验开始时间不能晚于结束时间。"""

    if start is None or end is None:
        return
    if _normalize_datetime(start) > _normalize_datetime(end):
        raise ValueError(f"{start_name} must be <= {end_name}")


def _normalize_datetime(value: datetime) -> datetime:
    """把 aware datetime 转成 UTC naive，避免混合比较报错。"""

    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
