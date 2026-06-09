from __future__ import annotations

from .types import NormalizedMobility


def normalize_mobility(description: str | None) -> NormalizedMobility:
    """从详情文本中提取签证、搬迁等海外岗位扩展信息。"""

    if description is None:
        return NormalizedMobility(False, False, None)

    lowered_text = description.casefold()
    has_visa_sponsorship = any(
        keyword in lowered_text
        for keyword in ("签证支持", "visa sponsorship", "sponsor visa", "work visa")
    )
    has_relocation_support = any(
        keyword in lowered_text
        for keyword in ("搬迁支持", "relocation support", "relocation package")
    )
    note_parts: list[str] = []
    if has_visa_sponsorship:
        note_parts.append("包含签证支持说明")
    if has_relocation_support:
        note_parts.append("包含搬迁支持说明")

    return NormalizedMobility(
        has_visa_sponsorship=has_visa_sponsorship,
        has_relocation_support=has_relocation_support,
        work_authorization_note="；".join(note_parts) if note_parts else None,
    )
