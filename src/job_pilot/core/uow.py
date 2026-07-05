from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SqlAlchemyUnitOfWork:
    """SQLAlchemy 事务工作单元，统一管理 session 生命周期和事务边界。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory
        self.session: AsyncSession | None = None
        self._finished: bool = False

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self._session_factory()
        self._finished = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = traceback
        if self.session is None:
            return

        try:
            if not self._finished:
                if exc_type is None and exc is None:
                    await self.commit()
                else:
                    await self.rollback()
        finally:
            await self.session.close()
            self.session = None

    async def commit(self) -> None:
        """提交当前事务。"""

        if self.session is None:
            raise RuntimeError("Unit of work session is not started")
        await self.session.commit()
        self._finished = True

    async def rollback(self) -> None:
        """回滚当前事务。"""

        if self.session is None:
            raise RuntimeError("Unit of work session is not started")
        await self.session.rollback()
        self._finished = True

    def require_session(self) -> AsyncSession:
        """读取当前工作单元 session。"""

        if self.session is None:
            raise RuntimeError("Unit of work session is not started")
        return self.session


UnitOfWorkFactory = Callable[[], SqlAlchemyUnitOfWork]


def build_sqlalchemy_uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> UnitOfWorkFactory:
    """构建 SQLAlchemy UoW 工厂，供 application 公开入口注入。"""

    return lambda: SqlAlchemyUnitOfWork(session_factory)
