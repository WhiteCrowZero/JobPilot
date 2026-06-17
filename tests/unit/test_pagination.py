from __future__ import annotations

from job_pilot.core.pagination import trim_page_items


def test_trim_page_items_returns_all_items_when_page_is_not_full() -> None:
    items, has_next = trim_page_items(("Python", "FastAPI"), page_size=3)

    assert items == ["Python", "FastAPI"]
    assert has_next is False


def test_trim_page_items_returns_exact_page_without_next_flag() -> None:
    items, has_next = trim_page_items([1, 2, 3], page_size=3)

    assert items == [1, 2, 3]
    assert has_next is False


def test_trim_page_items_drops_extra_item_and_marks_next_page() -> None:
    items, has_next = trim_page_items([1, 2, 3, 4], page_size=3)

    assert items == [1, 2, 3]
    assert has_next is True
