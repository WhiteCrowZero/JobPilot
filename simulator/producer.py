from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from celery import Celery

TASK_NAME = "job.import_raw"
QUEUE_NAME = "job.ingestion"
DEFAULT_BROKER_URL = "amqp://jobpilot:jobpilot_rabbitmq@127.0.0.1:15674//"
MESSAGE_DIR = Path(__file__).resolve().parent / "messages"
SCENARIO_FILES = {
    "new-job": "new-job.json",
    "duplicate-content": "duplicate-content.json",
    "changed-content": "changed-content.json",
}
REQUIRED_MESSAGE_FIELDS = {
    "schema_version",
    "event_type",
    "message_id",
    "trace_id",
    "producer",
    "produced_at",
    "source_platform",
    "raw_payload",
}


def build_producer(broker_url: str) -> Celery:
    """构造只连接 RabbitMQ 的独立 Celery producer。"""

    producer = Celery("jobpilot-crawler-simulator", broker=broker_url)
    producer.conf.update(
        task_serializer="json",
        accept_content=["json"],
        task_routes={TASK_NAME: {"queue": QUEUE_NAME}},
        task_default_queue="default",
    )
    return producer


def load_scenario_message(scenario: str) -> dict[str, object]:
    """读取固定 JSON 场景，并做 producer 侧的最小契约保护。"""

    message_path = MESSAGE_DIR / SCENARIO_FILES[scenario]
    message = json.loads(message_path.read_text(encoding="utf-8"))
    if not isinstance(message, dict):
        raise ValueError("scenario message must be a JSON object")

    missing_fields = REQUIRED_MESSAGE_FIELDS.difference(message)
    if missing_fields:
        raise ValueError(f"scenario message is missing fields: {sorted(missing_fields)}")
    if message["schema_version"] != 1:
        raise ValueError("simulator only supports schema_version=1")
    if message["event_type"] != "job.raw.collected":
        raise ValueError("simulator only supports job.raw.collected")
    return message


def send_scenario(*, scenario: str, broker_url: str) -> str:
    """按稳定 task/queue 契约发送一条模拟岗位消息。"""

    message = load_scenario_message(scenario)
    producer = build_producer(broker_url)
    result = producer.send_task(
        TASK_NAME,
        args=[message],
        queue=QUEUE_NAME,
        serializer="json",
    )
    return str(result.id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a raw job message to JobPilot RabbitMQ")
    parser.add_argument("scenario", choices=sorted(SCENARIO_FILES))
    args = parser.parse_args()

    broker_url = os.getenv("CELERY_BROKER_URL", DEFAULT_BROKER_URL)
    task_id = send_scenario(scenario=args.scenario, broker_url=broker_url)
    print(f"Sent {TASK_NAME} scenario={args.scenario} task_id={task_id}")


if __name__ == "__main__":
    main()
