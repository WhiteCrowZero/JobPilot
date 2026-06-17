from __future__ import annotations

from typing import Protocol


class SearchBackend(Protocol):
    async def health_check(self) -> bool: ...

    async def close(self) -> None: ...


class NullSearchBackend:
    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None
