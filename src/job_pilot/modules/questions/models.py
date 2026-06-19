from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from job_pilot.core.enums import enum_column
from job_pilot.db.base import Base, TimestampMixin
from job_pilot.modules.knowledge.enums import ContentSourceType
from job_pilot.modules.questions.enums import (
    QuestionAnswerStatus,
    QuestionDifficulty,
    QuestionReviewStatus,
    QuestionSkillRelation,
    QuestionStatus,
    QuestionType,
)

if TYPE_CHECKING:
    from job_pilot.modules.job_skills.models import Skill
    from job_pilot.modules.knowledge.models import KnowledgePoint
    from job_pilot.modules.study_tasks.models import StudyTaskQuestion
    from job_pilot.modules.users.models import User


class Question(TimestampMixin, Base):
    """公共题目表。

    支持开放面试题、单选、多选、判断
    题目去重只基于题干，不包含答案或选项。
    """

    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("question_hash", name="uq_questions_question_hash"),
        Index(
            "ix_questions_active_created_at_id",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'active' AND review_status = 'approved'"),
        ),
        Index(
            "ix_questions_active_type_difficulty_created",
            "question_type",
            "difficulty",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'active' AND review_status = 'approved'"),
        ),
        {"comment": "公共题目表，支持面试开放题、选择题（单选和多选）、判断题。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="题目主键 ID。",
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="题目标题，用于列表展示。",
    )

    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="题干正文。选择题选项不放在这里，放 question_options。",
    )

    question_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="题干去重 hash，基于规范化 question_text 生成 sha256，不包含答案和选项。",
    )

    question_type: Mapped[QuestionType] = mapped_column(
        enum_column(QuestionType, name="question_type", length=30),
        nullable=False,
        default=QuestionType.INTERVIEW_OPEN,
        server_default=QuestionType.INTERVIEW_OPEN.value,
        comment="题目类型：开放面试题、单选、多选、判断。",
    )

    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        enum_column(QuestionDifficulty, name="question_difficulty", length=20),
        nullable=False,
        default=QuestionDifficulty.MEDIUM,
        server_default=QuestionDifficulty.MEDIUM.value,
        comment="题目难度。",
    )

    status: Mapped[QuestionStatus] = mapped_column(
        enum_column(QuestionStatus, name="question_status", length=20),
        nullable=False,
        default=QuestionStatus.ACTIVE,
        server_default=QuestionStatus.ACTIVE.value,
        comment="题目状态。",
    )

    source_type: Mapped[ContentSourceType] = mapped_column(
        enum_column(ContentSourceType, name="question_source_type", length=30),
        nullable=False,
        default=ContentSourceType.OFFICIAL,
        server_default=ContentSourceType.OFFICIAL.value,
        comment="题目来源：official、user_supplement。",
    )

    source_note: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        comment="来源补充说明，不保存外部平台题目正文来源。",
    )

    review_status: Mapped[QuestionReviewStatus] = mapped_column(
        enum_column(QuestionReviewStatus, name="question_review_status", length=20),
        nullable=False,
        default=QuestionReviewStatus.APPROVED,
        server_default=QuestionReviewStatus.APPROVED.value,
        comment="审核状态。用户补充内容后续可先进入 draft。",
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="用户补充题目的创建者 ID。官方题目可为空。",
    )

    created_by_user: Mapped[User | None] = relationship(
        foreign_keys=[created_by_user_id],
    )

    options: Mapped[list[QuestionOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )

    answers: Mapped[list[QuestionAnswer]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )

    skill_links: Mapped[list[QuestionSkill]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )

    study_task_links: Mapped[list[StudyTaskQuestion]] = relationship(
        back_populates="question",
    )


class QuestionOption(TimestampMixin, Base):
    """选择题选项表。

    single_choice、multiple_choice、true_false 使用该表保存选项和正确答案。
    开放面试题通常不需要选项。
    """

    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint("question_id", "option_label", name="uq_question_options_question_label"),
        UniqueConstraint(
            "question_id", "sort_order", name="uq_question_options_question_sort_order"
        ),
        CheckConstraint("sort_order >= 0", name="ck_question_options_sort_order_non_negative"),
        {"comment": "题目选项表，支持单选、多选、判断题。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="选项主键 ID。",
    )

    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 questions.id。",
    )

    option_label: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="选项标识，例如 A、B、C、D、True、False。",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="选项内容。",
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="该选项是否为正确答案。单选/判断的正确选项数量由 service 校验。",
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="该选项为什么正确或错误的解释，可为空。",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=99,
        server_default="99",
        comment="选项展示顺序。",
    )

    question: Mapped[Question] = relationship(
        back_populates="options",
    )


class QuestionAnswer(TimestampMixin, Base):
    """题目答案表。

    主要服务于开放面试题。
    不区分 answer_type，避免主观分类过早固化。
    """

    __tablename__ = "question_answers"
    __table_args__ = (
        Index(
            "uq_question_answers_official",
            "question_id",
            unique=True,
            postgresql_where=text("source_type = 'official'"),
        ),
        Index(
            "ix_question_answers_question_active_source_created",
            "question_id",
            "source_type",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'active'"),
        ),
        {"comment": "题目答案表，支持同一题多个答案版本。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="答案主键 ID。",
    )

    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 questions.id。",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="答案内容。",
    )

    source_type: Mapped[ContentSourceType] = mapped_column(
        enum_column(ContentSourceType, name="question_answer_source_type", length=30),
        nullable=False,
        default=ContentSourceType.OFFICIAL,
        server_default=ContentSourceType.OFFICIAL.value,
        comment="答案来源：official、user_supplement。官方答案同一题只允许一个。",
    )

    status: Mapped[QuestionAnswerStatus] = mapped_column(
        enum_column(QuestionAnswerStatus, name="question_answer_status", length=20),
        nullable=False,
        default=QuestionAnswerStatus.ACTIVE,
        server_default=QuestionAnswerStatus.ACTIVE.value,
        comment="答案状态。",
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="用户补充答案的创建者 ID。",
    )

    question: Mapped[Question] = relationship(
        back_populates="answers",
    )

    created_by_user: Mapped[User | None] = relationship(
        foreign_keys=[created_by_user_id],
    )


class QuestionSkill(TimestampMixin, Base):
    """题目与技能/知识点关系表。"""

    __tablename__ = "question_skills"
    __table_args__ = (
        Index(
            "uq_question_skills_question_skill_no_knowledge",
            "question_id",
            "skill_id",
            unique=True,
            postgresql_where=text("knowledge_point_id IS NULL"),
        ),
        Index(
            "uq_question_skills_question_skill_knowledge",
            "question_id",
            "skill_id",
            "knowledge_point_id",
            unique=True,
            postgresql_where=text("knowledge_point_id IS NOT NULL"),
        ),
        Index(
            "uq_question_skills_primary_question",
            "question_id",
            unique=True,
            postgresql_where=text("relation = 'primary'"),
        ),
        Index("ix_question_skills_relation_question", "skill_id", "relation", "question_id"),
        Index("ix_question_skills_knowledge_point_question", "knowledge_point_id", "question_id"),
        {"comment": "题目与标准技能、知识点的关系表。"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="题目技能关系主键 ID。",
    )

    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 questions.id。",
    )

    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
        comment="关联标准技能 ID。",
    )

    knowledge_point_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联知识点 ID，可为空。",
    )

    relation: Mapped[QuestionSkillRelation] = mapped_column(
        enum_column(QuestionSkillRelation, name="question_skill_relation", length=20),
        nullable=False,
        default=QuestionSkillRelation.PRIMARY,
        server_default=QuestionSkillRelation.PRIMARY.value,
        comment="题目和技能的关联角色：primary 主技能，related 相关技能。",
    )

    question: Mapped[Question] = relationship(
        back_populates="skill_links",
    )

    skill: Mapped[Skill] = relationship(
        back_populates="question_links",
    )

    knowledge_point: Mapped[KnowledgePoint | None] = relationship(
        back_populates="question_links",
    )
