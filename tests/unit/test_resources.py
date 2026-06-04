from __future__ import annotations

import pytest

from job_pilot.core.config import settings
from job_pilot.core.resources import build_app_resources
from job_pilot.db.session import DatabaseResource


@pytest.mark.asyncio
async def test_build_app_resources_creates_application_resources() -> None:
    resources = build_app_resources(settings)

    try:
        assert isinstance(resources.database, DatabaseResource)
        assert resources.database.session_factory is not None
        assert resources.cache is not None
        assert resources.lock is not None
        assert resources.message_queue is not None
    finally:
        await resources.close()
