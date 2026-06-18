from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import false, or_
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

type TextSearchExpression = (
    ColumnElement[str | None] | InstrumentedAttribute[str] | InstrumentedAttribute[str | None]
)


class SearchBackend(Protocol):
    """搜索后端抽象，MVP 阶段只暴露 repository 需要的文本匹配能力。"""

    def contains_text(
        self,
        field: TextSearchExpression,
        keyword: str,
    ) -> ColumnElement[bool]:
        """构造单字段文本包含匹配条件。"""
        ...

    def contains_text_in_any_field(
        self,
        fields: Sequence[TextSearchExpression],
        keyword: str,
    ) -> ColumnElement[bool]:
        """构造多字段任一命中的文本匹配条件。"""
        ...

    def contains_any_text(
        self,
        field: TextSearchExpression,
        keywords: Sequence[str],
    ) -> ColumnElement[bool]:
        """构造单字段命中任一关键词的文本匹配条件。"""
        ...

    async def health_check(self) -> bool: ...

    async def close(self) -> None: ...


class SqlLikeSearchBackend:
    """基于 SQL LIKE 的 MVP 搜索后端。"""

    def contains_text(
        self,
        field: TextSearchExpression,
        keyword: str,
    ) -> ColumnElement[bool]:
        return field.ilike(self._to_contains_pattern(keyword), escape="\\")

    def contains_text_in_any_field(
        self,
        fields: Sequence[TextSearchExpression],
        keyword: str,
    ) -> ColumnElement[bool]:
        if not fields:
            return false()
        return or_(*(self.contains_text(field, keyword) for field in fields))

    def contains_any_text(
        self,
        field: TextSearchExpression,
        keywords: Sequence[str],
    ) -> ColumnElement[bool]:
        if not keywords:
            return false()
        return or_(*(self.contains_text(field, keyword) for keyword in keywords))

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    def _to_contains_pattern(self, keyword: str) -> str:
        """转换为安全的 LIKE contains pattern，避免 `%` 和 `_` 被当作通配符。"""

        escaped_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped_keyword}%"
