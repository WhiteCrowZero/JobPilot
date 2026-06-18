from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from job_pilot.core.pagination import PageParams, PageResult
from job_pilot.modules.knowledge.enums import KnowledgePointLevel, KnowledgePointStatus


class KnowledgeTreeNode(BaseModel):
    """知识点树节点响应。"""

    id: int
    title: str
    summary: str | None = None
    level: KnowledgePointLevel
    depth: int
    sort_order: int
    status: KnowledgePointStatus
    created_at: datetime
    updated_at: datetime
    children: list[KnowledgeTreeNode] = Field(default_factory=list)


class KnowledgeTreeResponse(BaseModel):
    """某个技能下的一组知识点树。"""

    skill_id: int
    tree: list[KnowledgeTreeNode]


class KnowledgeTreeParams(PageParams):
    """知识点树查询参数。"""

    skill_id: int | None = Field(default=None, ge=1)
    root_id: int | None = Field(default=None, ge=1)


class KnowledgeTreeListResponse(PageResult[KnowledgeTreeResponse]):
    """知识点树分页响应。"""


class KnowledgePointSearchParams(PageParams):
    """知识点筛选参数。"""

    keyword: str | None = Field(default=None, max_length=100)
    skill_id: int | None = Field(default=None, ge=1)
    levels: list[KnowledgePointLevel] | None = None


class KnowledgePointListItem(BaseModel):
    """知识点节点响应。"""

    id: int
    skill_id: int
    title: str
    summary: str | None = None
    level: KnowledgePointLevel
    created_at: datetime
    updated_at: datetime


class KnowledgePointListResponse(PageResult[KnowledgePointListItem]):
    """知识点分页响应。"""
