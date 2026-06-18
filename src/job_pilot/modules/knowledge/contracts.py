from __future__ import annotations

from dataclasses import dataclass

from job_pilot.core.contracts import PageQuery


@dataclass(slots=True, frozen=True)
class KnowledgeTreeQuery(PageQuery):
    """知识点树内部查询参数。"""

    skill_id: int | None = None
    parent_id: int | None = None
    include_archived: bool = False
