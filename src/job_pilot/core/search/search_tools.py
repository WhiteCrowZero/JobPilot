from __future__ import annotations


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned_value = value.strip()
    return cleaned_value or None


def clean_optional_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned_values = [value.strip() for value in values if value.strip()]
    return list(dict.fromkeys(cleaned_values))


def clean_optional_int_list(values: list[int] | None) -> list[int]:
    if not values:
        return []
    return list(dict.fromkeys(value for value in values if value > 0))
