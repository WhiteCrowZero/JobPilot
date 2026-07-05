from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from job_pilot.core.contracts import PageQuery
from job_pilot.modules.knowledge.enums import KnowledgePointLevel

KnowledgePointSort = Literal[
    "created_at_desc",
    "created_at_asc",
    "updated_at_desc",
    "updated_at_asc",
]


@dataclass(slots=True, frozen=True)
class KnowledgeTreeQuery(PageQuery):
    """知识点树内部查询参数。"""

    skill_id: int | None = None
    root_id: int | None = None


@dataclass(slots=True, frozen=True)
class KnowledgePointSearchQuery(PageQuery):
    """知识点搜索内部查询参数。"""

    keyword: str | None = None
    skill_id: int | None = None
    levels: list[KnowledgePointLevel] | None = None
    sort: KnowledgePointSort = "updated_at_desc"
