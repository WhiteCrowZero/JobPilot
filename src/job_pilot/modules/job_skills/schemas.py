from __future__ import annotations

from pydantic import BaseModel, Field

from job_pilot.core.pagination import PageParams, PageResult


class SkillLabelResponse(BaseModel):
    """对外返回的最小技能标签。"""

    id: int
    name: str


class SkillListItem(SkillLabelResponse):
    """技能列表项。用户侧暂不返回分类。"""


class SkillListParams(PageParams):
    """技能列表查询参数。"""

    keyword: str | None = Field(default=None, max_length=100)


class SkillListResponse(PageResult[SkillListItem]):
    """技能分页列表响应。"""
