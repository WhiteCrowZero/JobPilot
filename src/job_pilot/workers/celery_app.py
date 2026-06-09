from __future__ import annotations

import logging

from celery import Celery

from job_pilot.core.config import settings
from job_pilot.core.logging import configure_logging

configure_logging(settings, service_name="worker")
logger = logging.getLogger(__name__)

celery_app = Celery(
    "jobpilot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


@celery_app.task(name="debug.ping")
def ping() -> str:
    logger.info("Celery ping task executed")
    return "pong"
