from __future__ import annotations

import json
import logging
from pathlib import Path

from job_pilot.core.config import Settings
from job_pilot.core.logging import configure_logging, log_app_event


def test_configure_logging_routes_app_info_and_error_to_separate_files(tmp_path: Path) -> None:
    settings = Settings(
        APP_ENV="test",
        LOG_DIR=tmp_path,
        LOG_CONSOLE_ENABLED=False,
        LOG_FILE_ENABLED=True,
        LOG_LEVEL="INFO",
    )
    service_name = "unit_logging"
    logger = logging.getLogger("job_pilot.tests.logging")

    configure_logging(settings, service_name=service_name)
    try:
        log_app_event(logger, "Business event happened", extra={"event": "auth_login_failed"})
        logger.info("System lifecycle event happened")
        logger.error("System error happened")
    finally:
        for handler in logging.getLogger("job_pilot").handlers:
            handler.flush()

    log_dir = tmp_path / service_name
    app_records = _read_jsonl(log_dir / "app.jsonl")
    info_records = _read_jsonl(log_dir / "info.jsonl")
    error_records = _read_jsonl(log_dir / "error.jsonl")

    assert [record["message"] for record in app_records] == ["Business event happened"]
    assert app_records[0]["level"] == "APP"
    app_extra = app_records[0]["extra"]
    assert isinstance(app_extra, dict)
    assert app_extra["event"] == "auth_login_failed"
    assert [record["message"] for record in info_records] == ["System lifecycle event happened"]
    assert info_records[0]["level"] == "INFO"
    assert [record["message"] for record in error_records] == ["System error happened"]
    assert error_records[0]["level"] == "ERROR"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
