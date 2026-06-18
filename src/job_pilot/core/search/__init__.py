from __future__ import annotations

from job_pilot.core.search.backend import SearchBackend, SqlLikeSearchBackend, TextSearchExpression
from job_pilot.core.search.page_queries import (
    fetch_offset_page,
    fetch_page_ids,
    order_entities_by_ids,
)
from job_pilot.core.search.search_tools import (
    clean_optional_int_list,
    clean_optional_list,
    clean_optional_text,
)
from job_pilot.core.search.sorting import SortClauseFactory, SortMap, apply_sort_by_key

__all__ = [
    "SearchBackend",
    "SortClauseFactory",
    "SortMap",
    "SqlLikeSearchBackend",
    "TextSearchExpression",
    "apply_sort_by_key",
    "clean_optional_int_list",
    "clean_optional_list",
    "clean_optional_text",
    "fetch_offset_page",
    "fetch_page_ids",
    "order_entities_by_ids",
]
