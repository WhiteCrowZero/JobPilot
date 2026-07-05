from __future__ import annotations

from dataclasses import dataclass, field

from job_pilot.core.contracts import PageQuery


@dataclass(slots=True, frozen=True)
class JobCollectionFolderCreateCommand:
    """创建收藏夹内部命令。"""

    name: str
    sort_order: int = 99


@dataclass(slots=True, frozen=True)
class JobCollectionFolderUpdateCommand:
    """更新收藏夹内部命令。"""

    name: str | None = None
    sort_order: int | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class JobCollectionCreateCommand:
    """收藏岗位内部命令。"""

    job_post_id: int
    folder_id: int | None = None
    note: str | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class JobCollectionUpdateCommand:
    """更新岗位收藏内部命令。"""

    folder_id: int | None = None
    note: str | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class JobCollectionListQuery(PageQuery):
    """岗位收藏列表内部查询参数。"""

    folder_id: int | None = None
