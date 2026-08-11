from __future__ import annotations

from sqlalchemy.exc import OperationalError

from job_pilot.workers.celery_app import celery_app
from job_pilot.workers.tasks.import_raw_job import (
    MAX_RETRY_COUNTDOWN_SECONDS,
    build_log_correlation,
    build_retry_countdown,
    is_retryable_ingestion_error,
)


def test_celery_routes_raw_job_import_to_durable_ingestion_queue() -> None:
    queues = {queue.name: queue for queue in celery_app.conf.task_queues}

    assert celery_app.conf.task_default_queue == "default"
    assert set(queues) == {"default", "job.ingestion"}
    assert queues["job.ingestion"].durable is True
    assert celery_app.conf.task_routes["job.import_raw"] == {"queue": "job.ingestion"}
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]


def test_celery_registers_single_external_raw_job_task() -> None:
    celery_app.loader.import_default_modules()

    assert "job.import_raw" in celery_app.tasks
    assert "job.skill_sync" not in celery_app.tasks


def test_retry_classifier_only_accepts_transient_database_error() -> None:
    operational_error = OperationalError("SELECT 1", {}, ConnectionError("offline"))

    assert is_retryable_ingestion_error(operational_error) is True
    assert is_retryable_ingestion_error(ValueError("bad payload")) is False


def test_retry_countdown_is_bounded(monkeypatch) -> None:
    monkeypatch.setattr("random.uniform", lambda _start, _end: 0)

    assert build_retry_countdown(0) == 1
    assert build_retry_countdown(10) == MAX_RETRY_COUNTDOWN_SECONDS


def test_log_correlation_excludes_raw_payload() -> None:
    correlation = build_log_correlation(
        message_data={
            "message_id": "message-id",
            "trace_id": "trace-id",
            "raw_payload": {"secret": "must-not-log"},
        },
        task_id="task-id",
        raw_record_id=42,
    )

    assert correlation == {
        "task_id": "task-id",
        "trace_id": "trace-id",
        "message_id": "message-id",
        "raw_record_id": 42,
    }
