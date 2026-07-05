from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from job_pilot.modules.knowledge.enums import KnowledgePointLevel, KnowledgePointStatus


class KnowledgeTreeSnapshotNode(BaseModel):
    """知识点树缓存节点快照。"""

    id: int
    skill_id: int
    parent_id: int | None = None
    title: str
    summary: str | None = None
    level: KnowledgePointLevel
    depth: int
    sort_order: int
    status: KnowledgePointStatus
    created_at: datetime
    updated_at: datetime
