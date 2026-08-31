from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from job_pilot.modules.ingestion.adapters import MockJobAdapter
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.exceptions import UnsupportedJobSourcePlatformError
from job_pilot.modules.ingestion.sources import get_registered_job_source


def _valid_message_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_type": "job.raw.collected",
        "message_id": str(uuid4()),
        "trace_id": str(uuid4()),
        "producer": "jobpilot-simulator",
        "produced_at": datetime(2026, 8, 1, tzinfo=UTC),
        "fetched_at": datetime(2026, 8, 1, tzinfo=UTC),
        "source_platform": "mock",
        "external_job_id": "mock-10001",
        "source_url": "https://example.test/jobs/mock-10001",
        "raw_payload": {"title": "Python Backend Engineer", "skills": ["Python"]},
    }


def test_validate_raw_job_collected_message_accepts_strict_v1_json_contract() -> None:
    message = RawJobCollectedMessage.model_validate(_valid_message_data())

    assert message.schema_version == 1
    assert message.event_type == "job.raw.collected"
    assert message.model_dump(mode="json")["raw_payload"] == {
        "title": "Python Backend Engineer",
        "skills": ["Python"],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 2),
        ("event_type", "job.raw.updated"),
        ("message_id", "not-a-uuid"),
        ("trace_id", "not-a-uuid"),
        ("produced_at", datetime(2026, 8, 1)),
    ],
)
def test_validate_raw_job_collected_message_rejects_invalid_contract_field(
    field: str,
    value: object,
) -> None:
    data = {**_valid_message_data(), field: value}

    with pytest.raises(ValidationError):
        RawJobCollectedMessage.model_validate(data)


def test_validate_raw_job_collected_message_requires_source_identity() -> None:
    data = {**_valid_message_data(), "external_job_id": None, "source_url": None}

    with pytest.raises(ValidationError, match="external_job_id or source_url"):
        RawJobCollectedMessage.model_validate(data)


def test_validate_raw_job_collected_message_rejects_non_json_payload_value() -> None:
    data = {**_valid_message_data(), "raw_payload": {"invalid": object()}}

    with pytest.raises(ValidationError):
        RawJobCollectedMessage.model_validate(data)


def test_get_registered_job_source_returns_backend_owned_config_and_adapter() -> None:
    source = get_registered_job_source("mock")

    assert source.config.name == "JobPilot Simulator"
    assert source.config.base_url == "https://example.test/jobs"
    assert source.adapter_type is MockJobAdapter


def test_get_registered_job_source_rejects_unknown_platform() -> None:
    with pytest.raises(UnsupportedJobSourcePlatformError) as exc_info:
        get_registered_job_source("unknown")

    assert exc_info.value.code == "UNSUPPORTED_JOB_SOURCE_PLATFORM"
