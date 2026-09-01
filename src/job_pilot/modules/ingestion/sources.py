from __future__ import annotations

from dataclasses import dataclass

from job_pilot.modules.ingestion.adapters import (
    BaseJobAdapter,
    MockJobAdapter,
    TaotianJobAdapter,
    TencentJobAdapter,
)
from job_pilot.modules.ingestion.exceptions import UnsupportedJobSourcePlatformError


@dataclass(slots=True, frozen=True)
class JobSourceConfig:
    """后端维护的一次摄入来源配置。"""

    platform: str
    name: str
    base_url: str


@dataclass(slots=True, frozen=True)
class RegisteredJobSource:
    """稳定来源标识绑定的后端名称、根地址与 adapter。"""

    config: JobSourceConfig
    adapter_type: type[BaseJobAdapter]


SOURCE_REGISTRY: dict[str, RegisteredJobSource] = {
    "taotian": RegisteredJobSource(
        config=JobSourceConfig(
            platform="taotian",
            name="淘天招聘",
            base_url="https://talent.taotian.com",
        ),
        adapter_type=TaotianJobAdapter,
    ),
    "tencent": RegisteredJobSource(
        config=JobSourceConfig(
            platform="tencent",
            name="腾讯招聘",
            base_url="https://careers.tencent.com",
        ),
        adapter_type=TencentJobAdapter,
    ),
    "mock": RegisteredJobSource(
        config=JobSourceConfig(
            platform="mock",
            name="JobPilot Simulator",
            base_url="https://example.test/jobs",
        ),
        adapter_type=MockJobAdapter,
    ),
}


def get_registered_job_source(source_platform: str) -> RegisteredJobSource:
    """按稳定平台键读取后端来源配置。"""

    try:
        return SOURCE_REGISTRY[source_platform]
    except KeyError as exc:
        raise UnsupportedJobSourcePlatformError(source_platform) from exc
