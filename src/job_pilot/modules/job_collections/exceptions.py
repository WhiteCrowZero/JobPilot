from __future__ import annotations

from job_pilot.core.exceptions import ConflictError, NotFoundError


class JobPostForCollectionNotFoundError(NotFoundError):
    """收藏岗位不存在。"""

    def __init__(self, message: str = "Job post not found for collection"):
        super().__init__(message=message, code="JOB_COLLECTION_JOB_POST_NOT_FOUND")


class JobCollectionFolderNotFoundError(NotFoundError):
    """岗位收藏夹不存在。"""

    def __init__(self, message: str = "Job collection folder not found"):
        super().__init__(message=message, code="JOB_COLLECTION_FOLDER_NOT_FOUND")


class JobCollectionNotFoundError(NotFoundError):
    """岗位收藏不存在。"""

    def __init__(self, message: str = "Job collection not found"):
        super().__init__(message=message, code="JOB_COLLECTION_NOT_FOUND")


class DefaultJobCollectionFolderCannotArchiveError(ConflictError):
    """默认收藏夹不能归档。"""

    def __init__(self, message: str = "Default job collection folder cannot be archived"):
        super().__init__(
            message=message,
            code="DEFAULT_JOB_COLLECTION_FOLDER_CANNOT_ARCHIVE",
        )
