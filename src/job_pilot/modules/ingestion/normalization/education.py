from __future__ import annotations

from job_pilot.modules.job_posts.enums import EducationLevel

from .text import clean_text


def normalize_education_level(raw_education: object | None) -> EducationLevel:
    """把学历文本映射为统一枚举。"""

    education_text = clean_text(raw_education)
    if education_text is None:
        return EducationLevel.UNKNOWN

    lowered_text = education_text.casefold()
    if any(keyword in lowered_text for keyword in ("博士", "doctor", "phd")):
        return EducationLevel.DOCTOR
    if any(keyword in lowered_text for keyword in ("硕士", "研究生", "master", "postgraduate")):
        return EducationLevel.MASTER
    if any(keyword in lowered_text for keyword in ("本科", "bachelor", "undergraduate")):
        return EducationLevel.BACHELOR
    if any(keyword in lowered_text for keyword in ("大专", "专科", "associate", "college")):
        return EducationLevel.ASSOCIATE
    if any(keyword in lowered_text for keyword in ("不限", "无学历要求", "none", "not required")):
        return EducationLevel.NONE
    return EducationLevel.UNKNOWN
