from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from job_pilot.api.deps import JobPilotDep
from job_pilot.modules.knowledge.contracts import KnowledgeTreeQuery
from job_pilot.modules.knowledge.schemas import KnowledgeTreeListResponse, KnowledgeTreeParams

router = APIRouter()


@router.get("/tree", response_model=KnowledgeTreeListResponse)
async def read_knowledge_tree(
    pilot: JobPilotDep,
    params: Annotated[KnowledgeTreeParams, Query()],
) -> KnowledgeTreeListResponse:
    """查询知识点树。"""

    query = KnowledgeTreeQuery(
        skill_id=params.skill_id,
        parent_id=params.parent_id,
        include_archived=params.include_archived,
        page=params.page,
        page_size=params.page_size,
    )
    return await pilot.learning.get_knowledge_tree(query)
