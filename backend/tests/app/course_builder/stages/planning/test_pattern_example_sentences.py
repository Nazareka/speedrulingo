from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext
from course_builder.llm.unit_metadata_generation import graph as unit_metadata_generation_graph
from course_builder.queries.planning import CurriculumLesson, LessonWithPlan
from course_builder.stages.assembly.pattern_example_sentences import (
    SentenceAttachmentCandidate,
    _assign_sentence_candidates,
    persist_pattern_example_sentences,
)
from course_builder.stages.bootstrap.bootstrap_seed_words import insert_bootstrap_seed_words
from course_builder.stages.bootstrap.pattern_catalog import import_pattern_catalog
from course_builder.stages.bootstrap.sections import import_section_config
from course_builder.stages.bootstrap.theme_tags import import_theme_tags
from course_builder.stages.planning.normal_lesson_planning import plan_normal_lessons
from course_builder.stages.planning.section_curriculum_planning import persist_section_curriculum
from course_builder.stages.planning.unit_metadata_generation import generate_unit_metadata
from domain.content.models import Lesson, LessonSentence, Sentence
from tests.helpers.builder import create_test_build_context
from tests.helpers.fake_llms import SequentialStructuredLlm
from tests.helpers.scenarios import single_intro_unit_plan_payload
from tests.helpers.test_config_source import TEST_CONFIG_YAML


def _prepare_planned_course(
    db_session: Session,
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> BuildContext:
    context = create_test_build_context(db_session, tmp_path, content=TEST_CONFIG_YAML)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)

    unit_llm = SequentialStructuredLlm(payloads=[single_intro_unit_plan_payload()])
    monkeypatch.setattr(
        unit_metadata_generation_graph,
        "create_chat_openai",
        lambda *, model, reasoning_effort: unit_llm,
    )
    persist_section_curriculum(db_session, context=context)
    generate_unit_metadata(db_session, context=context)
    plan_normal_lessons(db_session, context=context)
    return context


def test_persist_pattern_example_sentences_persists_config_examples(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _prepare_planned_course(
        db_session,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    stats = persist_pattern_example_sentences(db_session, context=context)

    sentence_rows = (
        db_session.execute(select(Sentence).where(Sentence.course_version_id == context.course_version_id))
        .scalars()
        .all()
    )
    assert stats.sentences_created > 0
    assert stats.lesson_attachments_created > 0
    assert stats.word_links_created > 0
    assert stats.pattern_links_created > 0
    assert stats.sentence_units_created > 0
    assert sentence_rows
    assert all(sentence.target_pattern_id is not None for sentence in sentence_rows)
    assert db_session.scalar(select(LessonSentence.lesson_id).limit(1)) is not None


def test_persist_pattern_example_sentences_rejects_duplicate_attachment_for_same_lesson(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _prepare_planned_course(
        db_session,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    persist_pattern_example_sentences(db_session, context=context)

    with pytest.raises(ValueError, match="Configured pattern example sentence is duplicated within the same lesson"):
        persist_pattern_example_sentences(db_session, context=context)


def test_assign_sentence_candidates_respects_total_lesson_capacity(
    db_session: Session,
) -> None:
    lesson_one = Lesson(
        id="lesson-1",
        unit_id="unit-1",
        kind="normal",
        order_index=1,
        target_item_count=12,
    )
    lesson_two = Lesson(
        id="lesson-2",
        unit_id="unit-1",
        kind="normal",
        order_index=2,
        target_item_count=12,
    )
    lesson_rows = [
        LessonWithPlan(
            lesson=lesson_one,
            unit_order_index=1,
            planned_lesson=CurriculumLesson(
                lesson_index_within_unit=1,
                kind="normal",
                lesson_kind="unit_kernel",
                force_kana_display=False,
                target_item_count=12,
                introduced_word_lemmas=("学生",),
                kanji_focus_word_lemmas=("学生", "本", "先生", "日本人", "車", "水", "りんご"),
                target_word_lemmas=("学生",),
                target_pattern_codes=("WA_DESU_STATEMENT",),
                target_pattern_code="WA_DESU_STATEMENT",
                target_pattern_examples=(),
                available_word_lemmas=("学生",),
                available_pattern_codes=("WA_DESU_STATEMENT",),
                target_pattern_sentence_count=0,
            ),
        ),
        LessonWithPlan(
            lesson=lesson_two,
            unit_order_index=1,
            planned_lesson=CurriculumLesson(
                lesson_index_within_unit=2,
                kind="normal",
                lesson_kind="unit_expansion",
                force_kana_display=False,
                target_item_count=12,
                introduced_word_lemmas=(),
                kanji_focus_word_lemmas=(),
                target_word_lemmas=(),
                target_pattern_codes=("WA_DESU_STATEMENT",),
                target_pattern_code="WA_DESU_STATEMENT",
                target_pattern_examples=(),
                available_word_lemmas=("学生",),
                available_pattern_codes=("WA_DESU_STATEMENT",),
                target_pattern_sentence_count=0,
            ),
        ),
    ]

    assigned = _assign_sentence_candidates(
        lesson_rows=lesson_rows,
        generated_sentence_rows=[],
        pattern_candidates=[
            SentenceAttachmentCandidate(
                earliest_lesson_id="lesson-1",
                sentence_id="sentence-1",
                priority=0,
                sort_key="wa:1",
            )
        ],
        max_sentence_items_per_normal_lesson=5,
    )

    assert assigned == {"lesson-1": ["sentence-1"], "lesson-2": []}


def test_assign_sentence_candidates_can_spill_into_later_unit_normal_lessons() -> None:
    lesson_one = Lesson(
        id="lesson-1",
        unit_id="unit-1",
        kind="normal",
        order_index=1,
        target_item_count=12,
    )
    lesson_two = Lesson(
        id="lesson-2",
        unit_id="unit-2",
        kind="normal",
        order_index=1,
        target_item_count=12,
    )
    lesson_rows = [
        LessonWithPlan(
            lesson=lesson_one,
            unit_order_index=1,
            planned_lesson=CurriculumLesson(
                lesson_index_within_unit=1,
                kind="normal",
                lesson_kind="unit_kernel",
                force_kana_display=False,
                target_item_count=12,
                introduced_word_lemmas=("学生",),
                kanji_focus_word_lemmas=(),
                target_word_lemmas=("学生",),
                target_pattern_codes=("WA_DESU_STATEMENT",),
                target_pattern_code="WA_DESU_STATEMENT",
                target_pattern_examples=(),
                available_word_lemmas=("学生",),
                available_pattern_codes=("WA_DESU_STATEMENT",),
                target_pattern_sentence_count=0,
            ),
        ),
        LessonWithPlan(
            lesson=lesson_two,
            unit_order_index=2,
            planned_lesson=CurriculumLesson(
                lesson_index_within_unit=1,
                kind="normal",
                lesson_kind="unit_sentence_flow",
                force_kana_display=False,
                target_item_count=12,
                introduced_word_lemmas=(),
                kanji_focus_word_lemmas=(),
                target_word_lemmas=(),
                target_pattern_codes=(),
                target_pattern_code=None,
                target_pattern_examples=(),
                available_word_lemmas=("学生",),
                available_pattern_codes=("WA_DESU_STATEMENT",),
                target_pattern_sentence_count=0,
            ),
        ),
    ]

    assigned = _assign_sentence_candidates(
        lesson_rows=lesson_rows,
        generated_sentence_rows=[],
        pattern_candidates=[
            SentenceAttachmentCandidate(
                earliest_lesson_id="lesson-1",
                sentence_id="sentence-1",
                priority=0,
                sort_key="wa:1",
            ),
            SentenceAttachmentCandidate(
                earliest_lesson_id="lesson-1",
                sentence_id="sentence-2",
                priority=0,
                sort_key="wa:2",
            ),
            SentenceAttachmentCandidate(
                earliest_lesson_id="lesson-1",
                sentence_id="sentence-3",
                priority=0,
                sort_key="wa:3",
            ),
            SentenceAttachmentCandidate(
                earliest_lesson_id="lesson-1",
                sentence_id="sentence-4",
                priority=0,
                sort_key="wa:4",
            ),
        ],
        max_sentence_items_per_normal_lesson=3,
    )

    assert assigned == {
        "lesson-1": ["sentence-1", "sentence-2", "sentence-3"],
        "lesson-2": ["sentence-4"],
    }
