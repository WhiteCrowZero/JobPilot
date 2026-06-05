from __future__ import annotations

import re

E164_PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(phone: str) -> str:
    normalized_phone = phone.strip().replace(" ", "").replace("-", "")
    if not E164_PHONE_PATTERN.fullmatch(normalized_phone):
        raise ValueError("Phone must use E.164 format, for example +8613812345678")
    return normalized_phone
