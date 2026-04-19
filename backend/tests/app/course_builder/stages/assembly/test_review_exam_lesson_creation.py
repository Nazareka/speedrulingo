from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.queries.assembly import PatternPoolRow, WordPoolRow
from course_builder.stages.assembly.review_exam_lesson_creation import (
    SentenceSelectionRow,
    _select_sentence_window,
    create_algorithmic_review_exam_lessons,
)
from domain.content.models import Lesson, LessonPatternLink, LessonSentence, LessonWord, Unit
from tests.helpers.builder import create_test_build_context, load_test_config
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.pipeline import build_sentence_ready_course
from tests.helpers.scenarios import single_intro_unit_plan_payload

build_context = create_test_build_context
load_config = load_test_config


def review_exam_test_config() -> str:
    return build_test_config_yaml(
        updates={
            ("items", "review_previous_units", "item_count"): 2,
            ("items", "exam", "item_count"): 2,
        }
    )


def test_create_algorithmic_review_exam_lessons_persists_review_and_exam_lessons(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=review_exam_test_config())
    build_sentence_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    stats = create_algorithmic_review_exam_lessons(db_session, context=context)

    assert stats.review_lessons_created == 1
    assert stats.exam_lessons_created == 1
    assert stats.lessons_created == 2
    assert stats.lesson_words_created >= 1
    assert stats.lesson_pattern_links_created >= 1
    assert stats.lesson_sentences_created >= 1

    units = db_session.scalars(select(Unit).order_by(Unit.order_index)).all()
    for unit in units:
        lesson_kinds = list(
            db_session.scalars(select(Lesson.kind).where(Lesson.unit_id == unit.id).order_by(Lesson.order_index))
        )
        assert lesson_kinds[-2:] == ["review_previous_units", "exam"]

    assert (
        db_session.scalar(
            select(LessonWord.lesson_id)
            .join(Lesson, Lesson.id == LessonWord.lesson_id)
            .where(Lesson.kind.in_(["review_previous_units", "exam"]), LessonWord.role == "new")
            .limit(1)
        )
        is None
    )
    assert (
        db_session.scalar(select(LessonPatternLink.lesson_id).where(LessonPatternLink.role == "new").limit(1)) is None
    )

    assert len(units) == 1
    unit = units[0]
    review_lesson_id = db_session.scalar(
        select(Lesson.id).where(Lesson.unit_id == unit.id, Lesson.kind == "review_previous_units").limit(1)
    )
    assert review_lesson_id is not None
    review_sentence_ids = list(
        db_session.scalars(
            select(LessonSentence.sentence_id)
            .where(LessonSentence.lesson_id == review_lesson_id)
            .order_by(LessonSentence.order_index)
        )
    )
    assert len(review_sentence_ids) == 1
    review_source_unit_orders = set(
        db_session.scalars(
            select(Unit.order_index)
            .join(Lesson, Lesson.unit_id == Unit.id)
            .join(LessonSentence, LessonSentence.lesson_id == Lesson.id)
            .where(Lesson.kind == "normal", LessonSentence.sentence_id.in_(review_sentence_ids))
        )
    )
    assert review_source_unit_orders == {1}

    exam_lesson_id = db_session.scalar(
        select(Lesson.id).where(Lesson.unit_id == unit.id, Lesson.kind == "exam").limit(1)
    )
    assert exam_lesson_id is not None
    exam_sentence_ids = list(
        db_session.scalars(
            select(LessonSentence.sentence_id)
            .where(LessonSentence.lesson_id == exam_lesson_id)
            .order_by(LessonSentence.order_index)
        )
    )
    assert len(exam_sentence_ids) == 1
    exam_source_unit_orders = set(
        db_session.scalars(
            select(Unit.order_index)
            .join(Lesson, Lesson.unit_id == Unit.id)
            .join(LessonSentence, LessonSentence.lesson_id == Lesson.id)
            .where(Lesson.kind == "normal", LessonSentence.sentence_id.in_(exam_sentence_ids))
        )
    )
    assert exam_source_unit_orders == {1}


def test_select_sentence_window_allows_short_pool() -> None:
    sentence_rows = [
        SentenceSelectionRow(
            sentence_id="s1",
            source_unit_order_index=1,
            source_lesson_order_index=1,
            source_sentence_order_index=1,
        ),
        SentenceSelectionRow(
            sentence_id="s2",
            source_unit_order_index=1,
            source_lesson_order_index=2,
            source_sentence_order_index=1,
        ),
        SentenceSelectionRow(
            sentence_id="s3",
            source_unit_order_index=2,
            source_lesson_order_index=1,
            source_sentence_order_index=1,
        ),
        SentenceSelectionRow(
            sentence_id="s4",
            source_unit_order_index=2,
            source_lesson_order_index=3,
            source_sentence_order_index=1,
        ),
    ]

    assert _select_sentence_window(sentence_rows, target_count=6, window_index=0, window_count=2) == [
        "s1",
        "s2",
        "s3",
        "s4",
    ]
    assert _select_sentence_window(sentence_rows, target_count=6, window_index=1, window_count=2) == [
        "s3",
        "s4",
        "s1",
        "s2",
    ]


def test_create_algorithmic_review_exam_lessons_skips_exam_when_unit_has_no_current_unit_intro_content(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=review_exam_test_config())
    build_sentence_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    first_unit = db_session.scalar(select(Unit).order_by(Unit.order_index).limit(1))
    assert first_unit is not None
    second_unit = Unit(
        section_id=first_unit.section_id,
        order_index=first_unit.order_index + 10,
        title="Activation Only",
        description="No current-unit intro content.",
    )
    db_session.add(second_unit)
    db_session.flush()
    for order_index in range(1, 5):
        db_session.add(
            Lesson(
                unit_id=second_unit.id,
                order_index=order_index,
                kind="normal",
                target_item_count=2,
            )
        )
    db_session.commit()

    word_id = db_session.scalar(select(LessonWord.word_id).limit(1))
    pattern_id = db_session.scalar(select(LessonPatternLink.pattern_id).limit(1))
    sentence_id = db_session.scalar(select(LessonSentence.sentence_id).limit(1))
    assert word_id is not None
    assert pattern_id is not None
    assert sentence_id is not None

    def fake_list_word_pool(self: object, *, unit_ids: list[str]) -> list[WordPoolRow]:
        if unit_ids == [second_unit.id]:
            return []
        return [WordPoolRow(word_id=word_id, canonical_writing_ja="学生", intro_order=1)]

    def fake_list_pattern_pool(self: object, *, unit_ids: list[str]) -> list[PatternPoolRow]:
        if unit_ids == [second_unit.id]:
            return []
        return [PatternPoolRow(pattern_id=pattern_id, code="WA_DESU_STATEMENT", intro_order=1)]

    def fake_list_sentence_pool(self: object, *, unit_ids: list[str]) -> list[SentenceSelectionRow]:
        if unit_ids == [second_unit.id]:
            return []
        return [
            SentenceSelectionRow(
                sentence_id=sentence_id,
                source_unit_order_index=1,
                source_lesson_order_index=1,
                source_sentence_order_index=1,
            )
        ]

    monkeypatch.setattr("course_builder.queries.assembly.AssemblyQueries.list_word_pool", fake_list_word_pool)
    monkeypatch.setattr("course_builder.queries.assembly.AssemblyQueries.list_pattern_pool", fake_list_pattern_pool)
    monkeypatch.setattr("course_builder.queries.assembly.AssemblyQueries.list_sentence_pool", fake_list_sentence_pool)

    create_algorithmic_review_exam_lessons(db_session, context=context)

    units = db_session.scalars(select(Unit).order_by(Unit.order_index)).all()
    assert len(units) >= 2

    second_unit_lesson_kinds = list(
        db_session.scalars(select(Lesson.kind).where(Lesson.unit_id == second_unit.id).order_by(Lesson.order_index))
    )
    assert "exam" not in second_unit_lesson_kinds
