from __future__ import annotations

from enum import StrEnum


class KnowledgePointStatus(StrEnum):
    """知识点状态。"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class KnowledgePointLevel(StrEnum):
    """知识点难度层级。"""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ContentSourceType(StrEnum):
    """公共内容来源类型。"""

    AI = "ai"
    OFFICIAL = "official"
    USER_SUPPLEMENT = "user_supplement"
