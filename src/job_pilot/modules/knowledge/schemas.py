from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

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

    skill_id: int | None = None
    parent_id: int | None = None
    include_archived: bool = False

    @model_validator(mode="after")
    def validate_tree_scope(self) -> KnowledgeTreeParams:
        """限制一次请求只使用一种树起点。"""

        if self.skill_id is not None and self.parent_id is not None:
            raise ValueError("skill_id and parent_id cannot be set at the same time")
        return self


class KnowledgeTreeListResponse(PageResult[KnowledgeTreeResponse]):
    """知识点树分页响应。"""
