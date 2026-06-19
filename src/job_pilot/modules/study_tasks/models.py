from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, TimestampMixin, UserOwnedMixin
from job_pilot.modules.study_tasks.enums import (
    StudyTaskQuestionResult,
    StudyTaskQuestionStatus,
    StudyTaskSource,
    StudyTaskStatus,
    StudyTaskType,
)

if TYPE_CHECKING:
    from job_pilot.modules.job_skills.models import Skill
    from job_pilot.modules.questions.models import Question
    from job_pilot.modules.users.models import User


class StudyTask(UserOwnedMixin, TimestampMixin, Base):
    """用户学习任务主表。

    主表只保存任务本体，岗位/目标/技能匹配快照拆到 study_task_snapshots。
    """

    __tablename__ = "study_tasks"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_study_tasks_priority_range"),
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="ck_study_tasks_estimated_minutes_positive",
        ),
        CheckConstraint(
            "actual_minutes IS NULL OR actual_minutes >= 0",
            name="ck_study_tasks_actual_minutes_non_negative",
        ),
        CheckConstraint(
            "(status = 'todo' "
            "AND started_at IS NULL "
            "AND completed_at IS NULL "
            "AND archived_at IS NULL) "
            "OR (status = 'in_progress' AND completed_at IS NULL AND archived_at IS NULL) "
            "OR (status = 'completed' AND completed_at IS NOT NULL AND archived_at IS NULL) "
            "OR (status = 'archived' AND archived_at IS NOT NULL)",
            name="ck_study_tasks_status_timestamps",
        ),
        Index(
            "ix_study_tasks_user_status_priority_due",
            "user_id",
            "status",
            "priority",
            "due_date",
            text("created_at DESC"),
        ),
        Index("ix_study_tasks_user_skill_status", "user_id", "skill_id", "status"),
        Index(
            "uq_study_tasks_user_source_key_current",
            "user_id",
            "source_key",
            unique=True,
            postgresql_where=text("source_key IS NOT NULL AND status IN ('todo', 'in_progress')"),
        ),
        {"comment": "用户学习任务主表，承接目标岗位技能缺口并组织题目清单。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="任务主键 ID。"
    )

    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
        comment="任务对应的标准技能 ID。",
    )

    source: Mapped[StudyTaskSource] = mapped_column(
        enum_column(StudyTaskSource, name="study_task_source", length=40),
        nullable=False,
        default=StudyTaskSource.MANUAL,
        server_default=StudyTaskSource.MANUAL.value,
        comment="任务来源。",
    )

    source_key: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="任务生成幂等键，例如 target:12:skill:5:missing，由 service 生成。",
    )

    task_type: Mapped[StudyTaskType] = mapped_column(
        enum_column(StudyTaskType, name="study_task_type", length=30),
        nullable=False,
        default=StudyTaskType.QUESTION_PRACTICE,
        server_default=StudyTaskType.QUESTION_PRACTICE.value,
        comment="任务类型。",
    )

    status: Mapped[StudyTaskStatus] = mapped_column(
        enum_column(StudyTaskStatus, name="study_task_status", length=20),
        nullable=False,
        default=StudyTaskStatus.TODO,
        server_default=StudyTaskStatus.TODO.value,
        comment="任务状态。",
    )

    title: Mapped[str] = mapped_column(String(160), nullable=False, comment="任务标题。")

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="任务说明，保存任务目标和学习建议，不保存大段外部资料。",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
        comment="任务优先级，1 最高，5 最低。",
    )

    estimated_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="预计耗时，分钟。"
    )
    actual_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="实际耗时，分钟。"
    )
    planned_start_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="计划开始日期。"
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="计划完成日期。")

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="任务开始时间。"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="任务完成时间。"
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="任务归档时间。"
    )

    user: Mapped[User] = relationship(back_populates="study_tasks")
    skill: Mapped[Skill] = relationship(back_populates="study_tasks")

    snapshot: Mapped[StudyTaskSnapshot | None] = relationship(
        back_populates="study_task",
        cascade="all, delete-orphan",
        uselist=False,
    )
    progress: Mapped[StudyTaskProgress | None] = relationship(
        back_populates="study_task",
        cascade="all, delete-orphan",
        uselist=False,
    )
    questions: Mapped[list[StudyTaskQuestion]] = relationship(
        back_populates="study_task",
        cascade="all, delete-orphan",
    )
    attempts: Mapped[list[StudyTaskQuestionAttempt]] = relationship(back_populates="study_task")


class StudyTaskSnapshot(TimestampMixin, Base):
    """学习任务生成上下文快照表。"""

    __tablename__ = "study_task_snapshots"
    __table_args__ = (
        UniqueConstraint("study_task_id", name="uq_study_task_snapshots_task"),
        CheckConstraint(
            "required_level_snapshot IS NULL OR required_level_snapshot BETWEEN 1 AND 5",
            name="ck_study_task_snapshots_required_level_range",
        ),
        CheckConstraint(
            "user_level_snapshot IS NULL OR user_level_snapshot BETWEEN 1 AND 5",
            name="ck_study_task_snapshots_user_level_range",
        ),
        Index("ix_study_task_snapshots_target_job", "target_id", "job_post_id"),
        {"comment": "学习任务生成时的岗位、目标、技能缺口上下文快照。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="快照主键 ID。"
    )

    study_task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("study_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 study_tasks.id。",
    )

    target_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="生成时的目标岗位 ID 快照。"
    )
    job_post_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="生成时的岗位 ID 快照。"
    )

    skill_name_snapshot: Mapped[str] = mapped_column(
        String(120), nullable=False, comment="生成时技能名称快照。"
    )
    job_title_snapshot: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="生成时岗位标题快照。"
    )
    company_name_snapshot: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="生成时公司名称快照。"
    )
    target_title_snapshot: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="生成时目标标题快照。"
    )

    match_status_snapshot: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="生成时的技能覆盖状态快照，例如 missing、weak。",
    )
    required_level_snapshot: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="生成时 required_level 快照。"
    )
    user_level_snapshot: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="生成时用户技能等级快照。"
    )
    is_primary_target_snapshot: Mapped[bool | None] = mapped_column(
        nullable=True, comment="生成时是否主目标快照。"
    )
    target_priority_snapshot: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="生成时目标优先级快照。"
    )

    study_task: Mapped[StudyTask] = relationship(back_populates="snapshot")


class StudyTaskProgress(TimestampMixin, Base):
    """学习任务整体进度表。"""

    __tablename__ = "study_task_progress"
    __table_args__ = (
        UniqueConstraint("study_task_id", name="uq_study_task_progress_task"),
        CheckConstraint(
            "total_question_count >= 0", name="ck_study_task_progress_total_non_negative"
        ),
        CheckConstraint(
            "completed_question_count >= 0", name="ck_study_task_progress_completed_non_negative"
        ),
        CheckConstraint(
            "practiced_count >= 0", name="ck_study_task_progress_practiced_non_negative"
        ),
        CheckConstraint(
            "correct_count >= 0 AND incorrect_count >= 0 AND skipped_count >= 0",
            name="ck_study_task_progress_result_counts_non_negative",
        ),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_study_task_progress_percent_range",
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_study_task_progress_score_range",
        ),
        Index("ix_study_task_progress_user_updated", "user_id", text("updated_at DESC")),
        {"comment": "学习任务整体进度聚合表。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="进度主键 ID。"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户 ID。",
    )
    study_task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("study_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 study_tasks.id。",
    )

    total_question_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="任务题目总数。"
    )
    completed_question_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="已完成题目数。"
    )
    practiced_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="累计练习次数。"
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="累计正确次数。"
    )
    incorrect_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="累计错误次数。"
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="累计跳过次数。"
    )

    progress_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0, server_default="0", comment="任务进度百分比。"
    )
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="任务综合得分，0 到 100，可为空。"
    )
    last_practiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近练习时间。"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="任务进度完成时间。"
    )

    study_task: Mapped[StudyTask] = relationship(back_populates="progress")
    user: Mapped[User] = relationship()


class StudyTaskQuestion(TimestampMixin, Base):
    """学习任务内的题目清单与当前状态。"""

    __tablename__ = "study_task_questions"
    __table_args__ = (
        UniqueConstraint(
            "study_task_id", "question_id", name="uq_study_task_questions_task_question"
        ),
        CheckConstraint("sort_order >= 0", name="ck_study_task_questions_sort_order_non_negative"),
        CheckConstraint(
            "attempt_count >= 0", name="ck_study_task_questions_attempt_count_non_negative"
        ),
        CheckConstraint(
            "last_score IS NULL OR (last_score >= 0 AND last_score <= 100)",
            name="ck_study_task_questions_last_score_range",
        ),
        CheckConstraint(
            "(status = 'pending' AND completed_at IS NULL AND skipped_at IS NULL) "
            "OR (status = 'done' AND completed_at IS NOT NULL AND skipped_at IS NULL) "
            "OR (status = 'skipped' AND skipped_at IS NOT NULL)",
            name="ck_study_task_questions_status_timestamps",
        ),
        Index(
            "ix_study_task_questions_task_status_sort",
            "study_task_id",
            "status",
            "sort_order",
            "id",
        ),
        {"comment": "学习任务内题目清单，保存当前状态和最近一次练习摘要。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="任务题目主键 ID。"
    )
    study_task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("study_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 study_tasks.id。",
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
        comment="关联 questions.id。",
    )

    status: Mapped[StudyTaskQuestionStatus] = mapped_column(
        enum_column(StudyTaskQuestionStatus, name="study_task_question_status", length=20),
        nullable=False,
        default=StudyTaskQuestionStatus.PENDING,
        server_default=StudyTaskQuestionStatus.PENDING.value,
        comment="任务内题目当前状态。",
    )

    last_result: Mapped[StudyTaskQuestionResult | None] = mapped_column(
        enum_column(StudyTaskQuestionResult, name="study_task_question_result", length=20),
        nullable=True,
        comment="最近一次练习结果。",
    )
    last_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="最近一次练习得分。"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="练习次数。"
    )
    last_practiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近练习时间。"
    )

    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=99, server_default="99", comment="任务内题目顺序。"
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="题目加入任务时间。",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="题目完成时间。"
    )
    skipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="题目跳过时间。"
    )

    study_task: Mapped[StudyTask] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship(back_populates="study_task_links")
    attempts: Mapped[list[StudyTaskQuestionAttempt]] = relationship(
        back_populates="study_task_question", cascade="all, delete-orphan"
    )


class StudyTaskQuestionAttempt(TimestampMixin, Base):
    """学习任务内某道题的一次作答记录。

    该表用于保存多次作答历史，支持选择题、开放题题。
    """

    __tablename__ = "study_task_question_attempts"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_study_task_question_attempts_score_range",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_study_task_question_attempts_duration_non_negative",
        ),
        Index(
            "ix_study_task_question_attempts_user_task_attempted",
            "user_id",
            "study_task_id",
            text("attempted_at DESC"),
        ),
        Index(
            "ix_study_task_question_attempts_task_question_attempted",
            "study_task_question_id",
            text("attempted_at DESC"),
        ),
        {"comment": "学习任务内题目作答流水表，保存每次练习记录。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="作答记录主键 ID。"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户 ID。",
    )
    study_task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("study_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 study_tasks.id。",
    )
    study_task_question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("study_task_questions.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 study_task_questions.id。",
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
        comment="关联 questions.id，冗余保存便于查询。",
    )

    result: Mapped[StudyTaskQuestionResult] = mapped_column(
        enum_column(StudyTaskQuestionResult, name="study_task_question_attempt_result", length=20),
        nullable=False,
        comment="本次作答结果。",
    )
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="本次作答得分，0 到 100。"
    )
    selected_option_ids: Mapped[list[int] | None] = mapped_column(
        JSONB, nullable=True, comment="选择题本次选择的 option_id 列表。"
    )
    answer_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="简答题的本次作答内容。"
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="本次作答耗时，秒。"
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="作答时间。"
    )

    user: Mapped[User] = relationship()
    study_task: Mapped[StudyTask] = relationship(back_populates="attempts")
    study_task_question: Mapped[StudyTaskQuestion] = relationship(back_populates="attempts")
    question: Mapped[Question] = relationship()
