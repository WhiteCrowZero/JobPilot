from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import Enum as SAEnum


def enum_column(enum_cls: type[PyEnum], name: str, length: int) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=length,
        create_constraint=True,
        values_callable=lambda enum_values: [item.value for item in enum_values],
    )
