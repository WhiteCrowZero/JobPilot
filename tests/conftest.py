import os

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jobpilot-32-bytes")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://jobpilot:jobpilot@localhost:5433/jobpilot_test",
)
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://jobpilot:jobpilot@localhost:5433/jobpilot_test",
)
os.environ.setdefault("REDIS_URL", "redis://:jobpilot_redis@localhost:6389/10")
os.environ.setdefault("CELERY_BROKER_URL", "redis://:jobpilot_redis@localhost:6389/11")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://:jobpilot_redis@localhost:6389/12")


@pytest.fixture
def sample_user_id() -> int:
    return 1
