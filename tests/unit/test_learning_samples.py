from __future__ import annotations

from scripts.seed_learning_samples import (
    DEFAULT_KNOWLEDGE_POINTS,
    DEFAULT_QUESTIONS,
    DEFAULT_SKILLS,
    build_question_hash,
    normalize_question_text,
)


def test_learning_sample_questions_have_unique_hashes() -> None:
    """示例题库题干 hash 应保持唯一。"""

    hashes = [build_question_hash(item.question_text) for item in DEFAULT_QUESTIONS]

    assert len(hashes) == len(set(hashes))


def test_learning_sample_questions_reference_existing_skills_and_knowledge() -> None:
    """题目样本必须引用同批导入的技能和知识点。"""

    skill_names = {item.name for item in DEFAULT_SKILLS}
    knowledge_keys = {(item.skill_name, item.path) for item in DEFAULT_KNOWLEDGE_POINTS}

    for question in DEFAULT_QUESTIONS:
        assert question.skill_name in skill_names
        assert (question.skill_name, question.knowledge_path) in knowledge_keys


def test_normalize_question_text_collapses_case_and_whitespace() -> None:
    """题干归一化应消除大小写和多余空白差异。"""

    assert normalize_question_text("  FastAPI   Depends  ") == "fastapi depends"
