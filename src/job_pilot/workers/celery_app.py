from __future__ import annotations

from celery import Celery

from job_pilot.core.config import settings

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
    return "pong"
