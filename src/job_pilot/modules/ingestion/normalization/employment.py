from __future__ import annotations

from job_pilot.modules.job_posts.enums import EmploymentType

from .text import clean_text


def normalize_employment_type(raw_employment_type: object | None) -> EmploymentType:
    """把雇佣类型文本映射为统一枚举。"""

    employment_text = clean_text(raw_employment_type)
    if employment_text is None:
        return EmploymentType.UNKNOWN

    lowered_text = employment_text.casefold()
    if any(keyword in lowered_text for keyword in ("实习", "intern")):
        return EmploymentType.INTERNSHIP
    if any(keyword in lowered_text for keyword in ("兼职", "part-time", "part time")):
        return EmploymentType.PART_TIME
    if any(keyword in lowered_text for keyword in ("合同", "contract", "外包", "outsourcing")):
        return EmploymentType.CONTRACT
    if any(keyword in lowered_text for keyword in ("临时", "temporary")):
        return EmploymentType.TEMPORARY
    if any(keyword in lowered_text for keyword in ("自由", "freelance")):
        return EmploymentType.FREELANCE
    if any(keyword in lowered_text for keyword in ("全职", "full-time", "full time", "fulltime")):
        return EmploymentType.FULL_TIME
    return EmploymentType.UNKNOWN
