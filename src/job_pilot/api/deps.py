from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.db.session import get_db_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_session)]
