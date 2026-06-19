from __future__ import annotations

from job_pilot.core.exceptions import ValidationError


class JobDraftFieldRequiredError(ValidationError):
    """岗位草稿缺少必填字段。"""

    def __init__(self, field_name: str) -> None:
        super().__init__(
            message=f"Job draft {field_name} is required",
            code="JOB_DRAFT_FIELD_REQUIRED",
        )
