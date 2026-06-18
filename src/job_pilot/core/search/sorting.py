from __future__ import annotations

from collections.abc import Callable, Mapping

from sqlalchemy import Select
from sqlalchemy.sql.elements import ColumnElement

type SortClauseFactory = Callable[[], tuple[ColumnElement[object], ...]]
type SortMap = Mapping[str, SortClauseFactory]


def apply_sort_by_key[T: tuple[object, ...]](
    stmt: Select[T],
    *,
    sort_key: str,
    sort_map: SortMap,
    error_label: str,
) -> Select[T]:
    """按白名单 key 应用排序，非法 key 直接暴露内部调用错误。"""

    sort_clauses_factory = sort_map.get(sort_key)
    if sort_clauses_factory is None:
        raise ValueError(f"Unsupported {error_label} sort: {sort_key}")
    return stmt.order_by(*sort_clauses_factory())
