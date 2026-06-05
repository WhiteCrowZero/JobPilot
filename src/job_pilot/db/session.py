from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from job_pilot.core.config import Settings


@dataclass(slots=True)
class DatabaseResource:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    async def health_check(self) -> bool:
        try:
            async with self.session_factory() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar_one() == 1
        except Exception:
            return False

    async def close(self) -> None:
        await self.engine.dispose()


def build_database_resource(settings: Settings) -> DatabaseResource:
    engine = create_async_engine(
        settings.effective_database_url,
        echo=settings.DATABASE_ECHO,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    return DatabaseResource(
        engine=engine,
        session_factory=session_factory,
    )
