from __future__ import annotations

from pydantic import BaseModel, Field


class PageParams(BaseModel):
    """通用页码分页参数，供所有列表接口复用。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        """转换为数据库 offset。"""

        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """转换为数据库 limit。"""

        return self.page_size


class PageResult[T](BaseModel):
    """通用分页响应。

    TODO: MVP 阶段 total 可以返回 None，避免每个列表接口额外 count；
    后续接入 ES 后可用 ES 的近似 total 替代。
    """

    items: list[T]
    page: int
    page_size: int
    total: int | None = None
    has_next: bool | None = None
