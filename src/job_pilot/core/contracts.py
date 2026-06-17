from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PageQuery:
    """内部分页查询参数，避免 service/repository 依赖 HTTP schema。"""

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """转换为数据库 offset。"""

        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """转换为数据库 limit。"""

        return self.page_size
