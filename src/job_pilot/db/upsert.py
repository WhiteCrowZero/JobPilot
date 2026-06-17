from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.db.base import Base

UpsertValues = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class UpsertConflictTarget:
    """描述 PostgreSQL upsert 的冲突目标。"""

    constraint: str | None = None
    index_elements: Sequence[str] | None = None

    def __post_init__(self) -> None:
        if (self.constraint is None) == (self.index_elements is None):
            raise ValueError("Exactly one conflict target must be provided")

    @classmethod
    def by_constraint(cls, name: str) -> UpsertConflictTarget:
        """按唯一约束名定位冲突。"""

        return cls(constraint=name)

    @classmethod
    def by_index_elements(cls, elements: Sequence[str]) -> UpsertConflictTarget:
        """按唯一索引字段定位冲突。"""

        return cls(index_elements=elements)


def _merge_upsert_values(*groups: UpsertValues) -> dict[str, object]:
    """按传入顺序合并 upsert 字段，后面的字段覆盖前面的字段。"""

    merged_values: dict[str, object] = {}
    for group in groups:
        merged_values.update(group)
    return merged_values


async def _upsert_returning_record[T: Base](
    db: AsyncSession,
    *,
    model: type[T],
    conflict_target: UpsertConflictTarget,
    insert_values: UpsertValues,
    update_values: UpsertValues,
) -> T:
    """执行 PostgreSQL upsert，并返回 ORM 对象。

    适用于需要 `RETURNING model`、并希望刷新 session 中已有对象的 repository 方法。
    """

    conflict_values = update_values
    insert_stmt = pg_insert(model).values(**insert_values)

    if conflict_target.constraint is not None:
        conflict_stmt = insert_stmt.on_conflict_do_update(
            constraint=conflict_target.constraint,
            set_=conflict_values,
        )
    else:
        index_elements = conflict_target.index_elements
        if index_elements is None:
            raise ValueError("index_elements must be provided")
        conflict_stmt = insert_stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_=conflict_values,
        )

    result = await db.execute(
        conflict_stmt.returning(model).execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def upsert_restoring_record[T: Base](
    db: AsyncSession,
    *,
    model: type[T],
    conflict_constraint: str,
    identity_values: UpsertValues,
    create_values: UpsertValues,
    restore_values: UpsertValues,
    update_values: UpsertValues,
) -> T:
    """新增记录，或把软失效记录恢复为当前有效记录。

    `identity_values` 是唯一身份字段，例如 `user_id + job_post_id`。
    `create_values` 只用于新建，一般来自 schema 默认值。
    `restore_values` 同时用于新建和冲突恢复，例如 `status=active`、`removed_at=None`。
    `update_values` 只用于冲突恢复，一般来自 `exclude_unset=True` 的显式字段。
    """

    return await _upsert_returning_record(
        db,
        model=model,
        conflict_target=UpsertConflictTarget.by_constraint(conflict_constraint),
        insert_values=_merge_upsert_values(identity_values, restore_values, create_values),
        update_values=_merge_upsert_values(restore_values, update_values),
    )
