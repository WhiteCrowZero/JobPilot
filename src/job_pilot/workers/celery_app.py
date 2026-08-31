from __future__ import annotations

import logging

from celery import Celery
from kombu import Queue

from job_pilot.core.config import settings
from job_pilot.core.logging import configure_logging

configure_logging(settings, service_name="worker")
logger = logging.getLogger(__name__)

celery_app = Celery(
    "jobpilot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["job_pilot.workers.tasks.import_raw_job"],
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
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_queues=(
        Queue("default", durable=True),
        Queue("job.ingestion", durable=True),
    ),
    task_routes={
        "job.import_raw": {"queue": "job.ingestion"},
    },
    broker_transport_options={"confirm_publish": True},
)


@celery_app.task(name="debug.ping")
def ping() -> str:
    logger.info("Celery ping task executed")
    return "pong"
