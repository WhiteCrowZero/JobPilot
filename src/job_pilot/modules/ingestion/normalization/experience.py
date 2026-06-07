# ruff: noqa: E501
from __future__ import annotations

import re

from job_pilot.modules.job_posts.enums import ExperienceLevel

from .text import clean_text
from .types import NormalizedExperience

_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


def normalize_experience(raw_experience: object | None) -> NormalizedExperience:
    """解析经验文本为经验等级与年限范围。"""

    experience_text = clean_text(raw_experience)
    if experience_text is None:
        return NormalizedExperience(ExperienceLevel.UNKNOWN, None, None)

    lowered_text = experience_text.casefold()
    if any(
        keyword in lowered_text
        for keyword in ("不限", "无经验", "经验不限", "no experience", "not required")
    ):
        return NormalizedExperience(ExperienceLevel.NOT_APPLICABLE, None, None)
    if any(keyword in lowered_text for keyword in ("实习", "intern")):
        return NormalizedExperience(ExperienceLevel.INTERN, 0, 1)
    if any(keyword in lowered_text for keyword in ("应届", "graduate", "campus")):
        return NormalizedExperience(ExperienceLevel.ENTRY, 0, 1)

    years = [int(float(number)) for number in _NUMBER_PATTERN.findall(lowered_text)]
    if not years:
        return NormalizedExperience(ExperienceLevel.UNKNOWN, None, None)

    if any(
        keyword in lowered_text for keyword in ("以上", "及以上", "+", "至少", "minimum", "min")
    ):
        min_years = years[0]
        max_years = None
    elif any(
        keyword in lowered_text for keyword in ("以内", "以下", "不超过", "less than", "under")
    ):
        min_years = 0
        max_years = years[0]
    elif len(years) >= 2:
        min_years = min(years[0], years[1])
        max_years = max(years[0], years[1])
    else:
        min_years = years[0]
        max_years = years[0]

    return NormalizedExperience(
        experience_level=_classify_experience_level(min_years),
        experience_min_years=min_years,
        experience_max_years=max_years,
    )


def _classify_experience_level(min_years: int | None) -> ExperienceLevel:
    if min_years is None:
        return ExperienceLevel.UNKNOWN
    if min_years >= 8:
        return ExperienceLevel.LEAD
    if min_years >= 5:
        return ExperienceLevel.SENIOR
    if min_years >= 3:
        return ExperienceLevel.MID
    if min_years >= 1:
        return ExperienceLevel.JUNIOR
    return ExperienceLevel.ENTRY
