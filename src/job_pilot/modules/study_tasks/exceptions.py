from __future__ import annotations

from starlette import status

from job_pilot.core.exceptions import AppError, BadRequestError, NotFoundError


class StudyTaskNotFoundError(NotFoundError):
    """学习任务不存在或不属于当前用户。"""

    def __init__(self) -> None:
        super().__init__(
            message="Study task not found",
            code="STUDY_TASK_NOT_FOUND",
        )


class StudyTaskQuestionNotFoundError(NotFoundError):
    """任务题目不存在或不属于当前任务。"""

    def __init__(self) -> None:
        super().__init__(
            message="Study task question not found",
            code="STUDY_TASK_QUESTION_NOT_FOUND",
        )


class StudyTaskTargetNotFoundError(NotFoundError):
    """目标岗位不存在、不可用于生成学习任务，或不属于当前用户。"""

    def __init__(self) -> None:
        super().__init__(
            message="Study task target not found",
            code="STUDY_TASK_TARGET_NOT_FOUND",
        )


class StudyTaskSkillNotFoundError(NotFoundError):
    """手动创建学习任务时指定的技能不存在。"""

    def __init__(self) -> None:
        super().__init__(
            message="Study task skill not found",
            code="STUDY_TASK_SKILL_NOT_FOUND",
        )


class InvalidStudyTaskQuestionError(BadRequestError):
    """手动绑定的题目不满足学习任务要求。"""

    def __init__(self, message: str = "Invalid study task question") -> None:
        super().__init__(
            message=message,
            code="INVALID_STUDY_TASK_QUESTION",
        )


class InvalidStudyTaskAnswerPayloadError(BadRequestError):
    """提交作答的选项或文本载荷不合法。"""

    def __init__(self, message: str = "Invalid study task answer payload") -> None:
        super().__init__(
            message=message,
            code="INVALID_STUDY_TASK_ANSWER_PAYLOAD",
        )


class InvalidStudyTaskStatusTransitionError(BadRequestError):
    """学习任务状态流转不符合 MVP 规则。"""

    def __init__(self) -> None:
        super().__init__(
            message="Invalid study task status transition",
            code="INVALID_STUDY_TASK_STATUS_TRANSITION",
        )


class NoStudyTaskSkillGapAvailableError(BadRequestError):
    """目标岗位没有可生成任务的技能缺口。"""

    def __init__(self) -> None:
        super().__init__(
            message="No missing or weak skills are available for this target",
            code="NO_SKILL_GAP_AVAILABLE",
        )


class NoStudyTaskQuestionsAvailableError(BadRequestError):
    """技能缺口没有可用题目。"""

    def __init__(self) -> None:
        super().__init__(
            message="No approved questions are available for matched skills",
            code="NO_QUESTIONS_AVAILABLE",
        )


class StudyTaskQuestionTypeNotSupportedError(BadRequestError):
    """当前题型暂不支持自动提交作答。"""

    def __init__(self) -> None:
        super().__init__(
            message="This question type is not supported in MVP auto grading",
            code="QUESTION_TYPE_NOT_SUPPORTED",
        )


class StudyTaskOperationNotImplementedError(AppError):
    """学习任务接口已固定，但对应持久化逻辑尚未实现。"""

    def __init__(self, message: str = "Study task operation is not implemented yet") -> None:
        super().__init__(
            message=message,
            code="STUDY_TASK_OPERATION_NOT_IMPLEMENTED",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )
