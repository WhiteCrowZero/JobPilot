from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from job_pilot.api.deps import JobPilotDep
from job_pilot.modules.knowledge.contracts import KnowledgePointSearchQuery, KnowledgeTreeQuery
from job_pilot.modules.knowledge.schemas import (
    KnowledgePointListResponse,
    KnowledgePointSearchParams,
    KnowledgeTreeListResponse,
    KnowledgeTreeParams,
)

router = APIRouter()


@router.get("/tree", response_model=KnowledgeTreeListResponse)
async def read_knowledge_tree(
    pilot: JobPilotDep,
    params: Annotated[KnowledgeTreeParams, Query()],
) -> KnowledgeTreeListResponse:
    """查询知识点树。"""

    query = KnowledgeTreeQuery(
        skill_id=params.skill_id,
        root_id=params.root_id,
        page=params.page,
        page_size=params.page_size,
    )
    return await pilot.learning.get_knowledge_tree(query)


@router.get("/search", response_model=KnowledgePointListResponse)
async def search_knowledge_points(
    pilot: JobPilotDep,
    params: Annotated[KnowledgePointSearchParams, Query()],
) -> KnowledgePointListResponse:
    """按条件搜索知识点，返回普通分页列表。"""

    query = KnowledgePointSearchQuery(**params.model_dump())
    return await pilot.learning.search_knowledge_points(query)
