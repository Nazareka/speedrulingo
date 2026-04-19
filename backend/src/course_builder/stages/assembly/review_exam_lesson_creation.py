from __future__ import annotations

from dataclasses import dataclass
from math import floor

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext
from course_builder.queries.assembly import (
    AssemblyQueries,
    PatternPoolRow,
    SentenceSelectionRow,
    WordPoolRow,
)
from domain.content.models import (
    Lesson,
    LessonPatternLink,
    LessonSentence,
    LessonWord,
)


@dataclass(frozen=True, slots=True)
class ReviewExamLessonCreationStats:
    lessons_created: int
    review_lessons_created: int
    exam_lessons_created: int
    lesson_words_created: int
    lesson_pattern_links_created: int
    lesson_sentences_created: int


__all__ = [
    "ReviewExamLessonCreationStats",
    "SentenceSelectionRow",
    "create_algorithmic_review_exam_lessons",
]


@dataclass(frozen=True, slots=True)
class LessonContentCounters:
    lesson_words_created: int = 0
    lesson_pattern_links_created: int = 0
    lesson_sentences_created: int = 0


def _target_item_count_for_kind(*, context: BuildContext, lesson_kind: str) -> int:
    item_profile = (
        context.config.items.review_previous_units
        if lesson_kind == "review_previous_units"
        else context.config.items.exam
    )
    target_item_count = item_profile.item_count
    if target_item_count <= 0:
        msg = f"Lesson profile must define at least one item for kind={lesson_kind}"
        raise ValueError(msg)
    return target_item_count


def _lesson_kind_sentence_target_count(*, context: BuildContext, lesson_kind: str) -> int:
    target_item_count = _target_item_count_for_kind(context=context, lesson_kind=lesson_kind)
    return max(1, target_item_count // 2)


def _select_sentence_window(
    sentence_rows: list[SentenceSelectionRow],
    *,
    target_count: int,
    window_index: int,
    window_count: int,
) -> list[str]:
    if target_count <= 0:
        raise ValueError("Sentence target count must be positive")
    if not sentence_rows:
        return []
    start_index = floor((len(sentence_rows) * window_index) / max(1, window_count))
    rotated_rows = sentence_rows[start_index:] + sentence_rows[:start_index]
    return [row.sentence_id for row in rotated_rows[: min(target_count, len(rotated_rows))]]


def _load_sentence_pool_with_fallback(
    *,
    q: AssemblyQueries,
    preferred_unit_ids: list[str],
    fallback_unit_ids: list[str],
    target_count: int,
) -> list[SentenceSelectionRow]:
    sentence_pool = q.list_sentence_pool(unit_ids=preferred_unit_ids)
    if len(sentence_pool) >= target_count or not fallback_unit_ids:
        return sentence_pool

    fallback_pool = q.list_sentence_pool(unit_ids=fallback_unit_ids)
    combined_by_sentence_id: dict[str, SentenceSelectionRow] = {row.sentence_id: row for row in sentence_pool}
    for row in fallback_pool:
        combined_by_sentence_id.setdefault(row.sentence_id, row)
    return sorted(
        combined_by_sentence_id.values(),
        key=lambda row: (
            row.source_unit_order_index,
            row.source_lesson_order_index,
            row.source_sentence_order_index,
            row.sentence_id,
        ),
    )


def _attach_lesson_words(
    db: Session,
    *,
    lesson_id: str,
    word_pool: list[WordPoolRow],
) -> int:
    created_count = 0
    for word in word_pool:
        db.add(
            LessonWord(
                lesson_id=lesson_id,
                word_id=word.word_id,
                role="review",
            )
        )
        created_count += 1
    return created_count


def _attach_lesson_patterns(
    db: Session,
    *,
    lesson_id: str,
    pattern_pool: list[PatternPoolRow],
    role: str,
) -> int:
    created_count = 0
    for pattern in pattern_pool:
        db.add(
            LessonPatternLink(
                lesson_id=lesson_id,
                pattern_id=pattern.pattern_id,
                role=role,
            )
        )
        created_count += 1
    return created_count


def _attach_lesson_sentences(
    db: Session,
    *,
    lesson_id: str,
    sentence_ids: list[str],
    role: str,
) -> int:
    created_count = 0
    for sentence_order_index, sentence_id in enumerate(sentence_ids, start=1):
        db.add(
            LessonSentence(
                lesson_id=lesson_id,
                sentence_id=sentence_id,
                order_index=sentence_order_index,
                role=role,
            )
        )
        created_count += 1
    return created_count


def _has_attachable_content(
    *,
    word_pool: list[WordPoolRow],
    pattern_pool: list[PatternPoolRow],
    sentence_ids: list[str],
) -> bool:
    return bool(word_pool or pattern_pool or sentence_ids)


def create_algorithmic_review_exam_lessons(
    db: Session,
    *,
    context: BuildContext,
) -> ReviewExamLessonCreationStats:
    q = AssemblyQueries(db, context.course_version_id, context.section_code)
    section = q.get_section()
    if section is None:
        msg = (
            "Section config must exist before algorithmic review/exam lesson creation "
            f"for course_version_id={context.course_version_id}"
        )
        raise ValueError(msg)

    units = q.list_units_for_section(section_id=section.id)
    if not units:
        msg = f"Units must exist before review/exam lesson creation for course_version_id={context.course_version_id}"
        raise ValueError(msg)

    if q.exists_non_normal_lessons_for_section(section_id=section.id):
        msg = f"Review/exam lessons already exist for course_version_id={context.course_version_id}"
        raise ValueError(msg)

    lessons_created = 0
    review_lessons_created = 0
    exam_lessons_created = 0
    lesson_words_created = 0
    lesson_pattern_links_created = 0
    lesson_sentences_created = 0

    try:
        for unit in units:
            persisted_normal_order_indices = q.list_normal_lesson_order_indices_for_unit(unit_id=unit.id)
            if not persisted_normal_order_indices or persisted_normal_order_indices != list(
                range(1, len(persisted_normal_order_indices) + 1)
            ):
                msg = (
                    f"Unit {unit.id} does not have contiguous normal lesson order indices starting at 1: "
                    f"{persisted_normal_order_indices}"
                )
                raise ValueError(msg)
            review_order_indices = list(
                range(
                    len(persisted_normal_order_indices) + 1,
                    len(persisted_normal_order_indices) + context.config.lessons.review_previous_units_lessons_per_unit + 1,
                )
            )
            exam_order_index = review_order_indices[-1] + 1 if review_order_indices else len(persisted_normal_order_indices) + 1

            previous_units = [candidate for candidate in units if candidate.order_index < unit.order_index]
            review_source_units = previous_units if previous_units else [unit]
            review_source_unit_ids = [candidate.id for candidate in review_source_units]
            exam_source_unit_ids = [unit.id]

            review_word_pool = q.list_word_pool(unit_ids=review_source_unit_ids)
            exam_word_pool = q.list_word_pool(unit_ids=exam_source_unit_ids)
            review_pattern_pool = q.list_pattern_pool(unit_ids=review_source_unit_ids)
            exam_pattern_pool = q.list_pattern_pool(unit_ids=exam_source_unit_ids)

            review_target_item_count = _target_item_count_for_kind(
                context=context,
                lesson_kind="review_previous_units",
            )
            exam_target_item_count = _target_item_count_for_kind(
                context=context,
                lesson_kind="exam",
            )
            review_sentence_pool = _load_sentence_pool_with_fallback(
                q=q,
                preferred_unit_ids=review_source_unit_ids,
                fallback_unit_ids=[] if previous_units else exam_source_unit_ids,
                target_count=_lesson_kind_sentence_target_count(
                    context=context,
                    lesson_kind="review_previous_units",
                ),
            )
            exam_sentence_pool = _load_sentence_pool_with_fallback(
                q=q,
                preferred_unit_ids=exam_source_unit_ids,
                fallback_unit_ids=[],
                target_count=_lesson_kind_sentence_target_count(context=context, lesson_kind="exam"),
            )

            for review_lesson_index, lesson_order_index in enumerate(review_order_indices):
                selected_sentence_ids: list[str] = []
                if review_sentence_pool:
                    selected_sentence_ids = _select_sentence_window(
                        review_sentence_pool,
                        target_count=_lesson_kind_sentence_target_count(
                            context=context,
                            lesson_kind="review_previous_units",
                        ),
                        window_index=review_lesson_index,
                        window_count=max(1, len(review_order_indices)),
                    )
                if not _has_attachable_content(
                    word_pool=review_word_pool,
                    pattern_pool=review_pattern_pool,
                    sentence_ids=selected_sentence_ids,
                ):
                    continue
                lesson_row = Lesson(
                    unit_id=unit.id,
                    order_index=lesson_order_index,
                    kind="review_previous_units",
                    target_item_count=review_target_item_count,
                )
                db.add(lesson_row)
                db.flush()
                lessons_created += 1
                review_lessons_created += 1

                lesson_words_created += _attach_lesson_words(
                    db,
                    lesson_id=lesson_row.id,
                    word_pool=review_word_pool,
                )
                lesson_pattern_links_created += _attach_lesson_patterns(
                    db,
                    lesson_id=lesson_row.id,
                    pattern_pool=review_pattern_pool,
                    role="review",
                )

                if selected_sentence_ids:
                    lesson_sentences_created += _attach_lesson_sentences(
                        db,
                        lesson_id=lesson_row.id,
                        sentence_ids=selected_sentence_ids,
                        role="review",
                    )

            selected_exam_sentence_ids: list[str] = []
            if exam_sentence_pool:
                selected_exam_sentence_ids = _select_sentence_window(
                    exam_sentence_pool,
                    target_count=_lesson_kind_sentence_target_count(context=context, lesson_kind="exam"),
                    window_index=0,
                    window_count=1,
                )
            if not _has_attachable_content(
                word_pool=exam_word_pool,
                pattern_pool=exam_pattern_pool,
                sentence_ids=selected_exam_sentence_ids,
            ):
                continue

            exam_lesson = Lesson(
                unit_id=unit.id,
                order_index=exam_order_index,
                kind="exam",
                target_item_count=exam_target_item_count,
            )
            db.add(exam_lesson)
            db.flush()
            lessons_created += 1
            exam_lessons_created += 1

            lesson_words_created += _attach_lesson_words(
                db,
                lesson_id=exam_lesson.id,
                word_pool=exam_word_pool,
            )
            lesson_pattern_links_created += _attach_lesson_patterns(
                db,
                lesson_id=exam_lesson.id,
                pattern_pool=exam_pattern_pool,
                role="mastery",
            )

            if selected_exam_sentence_ids:
                lesson_sentences_created += _attach_lesson_sentences(
                    db,
                    lesson_id=exam_lesson.id,
                    sentence_ids=selected_exam_sentence_ids,
                    role="review",
                )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return ReviewExamLessonCreationStats(
        lessons_created=lessons_created,
        review_lessons_created=review_lessons_created,
        exam_lessons_created=exam_lessons_created,
        lesson_words_created=lesson_words_created,
        lesson_pattern_links_created=lesson_pattern_links_created,
        lesson_sentences_created=lesson_sentences_created,
    )
