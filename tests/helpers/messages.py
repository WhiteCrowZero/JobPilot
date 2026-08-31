from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue

from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage

TEST_PRODUCED_AT = datetime(2026, 8, 1, tzinfo=UTC)


def stable_test_uuid(value: str) -> str:
    """用可读测试标识生成稳定 UUID。"""

    return str(uuid5(NAMESPACE_URL, f"https://jobpilot.test/{value}"))


def build_test_raw_job_message(
    *,
    message_id: str,
    source_platform: str,
    external_job_id: str | None,
    source_url: str | None,
    producer: str,
    raw_payload: dict[str, JsonValue],
    trace_id: str | None = None,
) -> RawJobCollectedMessage:
    """构造满足严格 V1 契约的测试消息。"""

    return RawJobCollectedMessage(
        schema_version=1,
        event_type="job.raw.collected",
        message_id=stable_test_uuid(message_id),
        trace_id=stable_test_uuid(trace_id or f"trace:{message_id}"),
        producer=producer,
        produced_at=TEST_PRODUCED_AT,
        fetched_at=TEST_PRODUCED_AT,
        source_platform=source_platform,
        external_job_id=external_job_id,
        source_url=source_url,
        raw_payload=raw_payload,
    )
