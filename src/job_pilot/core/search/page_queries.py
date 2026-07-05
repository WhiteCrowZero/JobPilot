from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_offset_page[T](
    db: AsyncSession,
    stmt: Select[tuple[T]],
    *,
    offset: int,
    limit: int,
) -> list[T]:
    """执行 offset + limit + 1 分页查询，调用方负责裁剪 has_next。"""

    result = await db.execute(stmt.offset(offset).limit(limit + 1))
    return list(result.scalars().all())


async def fetch_page_ids(
    db: AsyncSession,
    stmt: Select[tuple[int]],
    *,
    offset: int,
    limit: int,
) -> list[int]:
    """执行 ID 分页查询，适合重列表先分页再批量加载实体。"""

    return await fetch_offset_page(db, stmt, offset=offset, limit=limit)


def order_entities_by_ids[T](
    ids: Sequence[int],
    entities: Iterable[T],
    *,
    get_id: Callable[[T], int],
) -> list[T]:
    """按分页 ID 顺序保序返回实体。"""

    entity_by_id = {get_id(entity): entity for entity in entities}
    return [entity_by_id[item_id] for item_id in ids if item_id in entity_by_id]
