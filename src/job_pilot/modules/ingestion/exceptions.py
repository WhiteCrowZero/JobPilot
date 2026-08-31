from __future__ import annotations

from job_pilot.core.exceptions import BadRequestError, ValidationError


class UnsupportedJobSourcePlatformError(BadRequestError):
    """消息声明了后端未注册的来源平台。"""

    def __init__(self, source_platform: str) -> None:
        super().__init__(
            message=f"Unsupported job source platform: {source_platform}",
            code="UNSUPPORTED_JOB_SOURCE_PLATFORM",
        )


class JobDraftFieldRequiredError(ValidationError):
    """岗位草稿缺少必填字段。"""

    def __init__(self, field_name: str) -> None:
        super().__init__(
            message=f"Job draft {field_name} is required",
            code="JOB_DRAFT_FIELD_REQUIRED",
        )
