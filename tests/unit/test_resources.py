from __future__ import annotations

import pytest

from job_pilot.core.config import settings
from job_pilot.core.exceptions import ResourceUnavailableError
from job_pilot.core.resources import build_app_resources, build_database_only_resources
from job_pilot.db.session import DatabaseResource


@pytest.mark.asyncio
async def test_build_app_resources_creates_application_resources() -> None:
    resources = build_app_resources(settings)

    try:
        assert isinstance(resources.database, DatabaseResource)
        assert resources.require_database().session_factory is not None
        assert resources.cache is not None
        assert resources.lock is not None
    finally:
        await resources.close()


@pytest.mark.asyncio
async def test_build_database_only_resources_keeps_optional_resources_empty() -> None:
    resources = build_database_only_resources(settings)

    try:
        assert isinstance(resources.require_database(), DatabaseResource)
        assert resources.redis_client is None
        assert resources.cache is None
        assert resources.lock is None

        with pytest.raises(ResourceUnavailableError):
            resources.require_cache()
    finally:
        await resources.close()
