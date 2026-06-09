from __future__ import annotations

from job_pilot.modules.job_posts.enums import WorkplaceType

from .text import clean_text


def normalize_workplace_type(
    *,
    raw_flexibility: object | None,
    raw_location_text: object | None,
) -> WorkplaceType:
    """把办公方式文本映射为统一枚举。"""

    combined_text = " ".join(
        text
        for text in (
            clean_text(raw_flexibility),
            clean_text(raw_location_text),
        )
        if text is not None
    ).casefold()

    if not combined_text:
        return WorkplaceType.UNKNOWN
    if any(keyword in combined_text for keyword in ("远程", "remote", "work from home", "wfh")):
        return WorkplaceType.REMOTE
    if any(keyword in combined_text for keyword in ("混合", "hybrid")):
        return WorkplaceType.HYBRID
    if any(keyword in combined_text for keyword in ("到岗", "现场", "坐班", "onsite", "office")):
        return WorkplaceType.ONSITE
    return WorkplaceType.UNKNOWN
