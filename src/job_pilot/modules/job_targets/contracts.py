from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from job_pilot.core.contracts import PageQuery
from job_pilot.modules.job_targets.enums import JobTargetStatus


@dataclass(slots=True, frozen=True)
class JobTargetCreateCommand:
    """新增目标岗位内部命令。"""

    job_post_id: int
    source_collection_id: int | None = None
    priority: int = 3
    is_primary: bool = False
    note: str | None = None
    target_date: date | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class JobTargetUpdateCommand:
    """更新目标岗位内部命令。"""

    status: JobTargetStatus | None = None
    priority: int | None = None
    is_primary: bool | None = None
    note: str | None = None
    target_date: date | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class JobTargetListQuery(PageQuery):
    """目标岗位列表内部查询参数。"""

    statuses: list[JobTargetStatus] | None = None
