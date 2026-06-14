from __future__ import annotations

from enum import StrEnum


class JobCollectionFolderStatus(StrEnum):
    """岗位收藏夹状态。"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class JobCollectionStatus(StrEnum):
    """岗位收藏状态。"""

    ACTIVE = "active"
    REMOVED = "removed"
