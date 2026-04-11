from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext
from course_builder.queries.release import ReleaseQueries
from course_builder.stages.planning.section_curriculum import MAX_NORMAL_LESSONS_PER_UNIT, MIN_NORMAL_LESSONS_PER_UNIT


@dataclass(frozen=True, slots=True)
class SectionAcceptanceStats:
    section_id: str
    accepted: bool
    unit_count: int
    lesson_count: int
    item_count: int


def run_section_acceptance_checks(
    db: Session,
    *,
    context: BuildContext,
) -> SectionAcceptanceStats:
    q = ReleaseQueries(db, context.course_version_id, context.section_code)
    section = q.get_section()
    if section is None:
        msg = f"Section config must exist before section acceptance checks for course_version_id={context.course_version_id}"
        raise ValueError(msg)

    units = q.list_units_for_section(section_id=section.id)
    unit_count = len(units)
    if unit_count != section.target_unit_count:
        msg = f"Section unit count is wrong: {unit_count} != {section.target_unit_count}"
        raise ValueError(msg)

    minimum_normal_lessons = MIN_NORMAL_LESSONS_PER_UNIT
    maximum_normal_lessons = MAX_NORMAL_LESSONS_PER_UNIT
    expected_review_lessons = context.config.lessons.review_previous_units_lessons_per_unit
    expected_exam_lessons = context.config.lessons.exam_lessons_per_unit

    total_lesson_count = 0
    total_item_count = 0

    missing_payload_count = q.count_items_missing_payloads_for_section(section_id=section.id)
    if missing_payload_count > 0:
        msg = f"Section has items with missing payload rows: {missing_payload_count}"
        raise ValueError(msg)
    missing_word_intro_count = q.count_new_words_missing_word_choice_intro_for_section(section_id=section.id)
    if missing_word_intro_count > 0:
        msg = f"Section has new words without any word_choice intro: {missing_word_intro_count}"
        raise ValueError(msg)
    missing_sentence_intro_count = q.count_section_sentences_missing_normal_lesson_intro(section_id=section.id)
    if missing_sentence_intro_count > 0:
        msg = f"Section has section-owned sentences missing a normal-lesson intro: {missing_sentence_intro_count}"
        raise ValueError(msg)
    repeated_word_intro_count = q.count_words_with_multiple_normal_word_choice_intros_for_section(section_id=section.id)
    if repeated_word_intro_count > 0:
        msg = f"Section has words with repeated normal-lesson word_choice intros: {repeated_word_intro_count}"
        raise ValueError(msg)
    repeated_sentence_intro_count = q.count_sentences_with_multiple_normal_intro_lessons_for_section(section_id=section.id)
    if repeated_sentence_intro_count > 0:
        msg = f"Section has sentences with repeated normal-lesson introductions: {repeated_sentence_intro_count}"
        raise ValueError(msg)
    incomplete_sentence_intro_count = q.count_normal_sentence_intros_missing_bidirectional_items_for_section(
        section_id=section.id
    )
    if incomplete_sentence_intro_count > 0:
        msg = (
            "Section has normal sentence introductions without exactly one ja->en and one en->ja item: "
            f"{incomplete_sentence_intro_count}"
        )
        raise ValueError(msg)
    missing_surfaced_sentence_count = q.count_normal_lesson_sentences_never_surfaced_for_section(section_id=section.id)
    if missing_surfaced_sentence_count > 0:
        msg = f"Section has normal lesson sentences that never surface in items: {missing_surfaced_sentence_count}"
        raise ValueError(msg)
    review_current_unit_content_count = q.count_review_lessons_with_current_unit_content(section_id=section.id)
    if review_current_unit_content_count > 0:
        msg = f"Section has review lessons containing current-unit content: {review_current_unit_content_count}"
        raise ValueError(msg)
    exam_previous_unit_content_count = q.count_exam_lessons_with_previous_unit_content(section_id=section.id)
    if exam_previous_unit_content_count > 0:
        msg = f"Section has exam lessons containing previous-unit content: {exam_previous_unit_content_count}"
        raise ValueError(msg)

    for unit in units:
        lessons = q.list_lessons_for_unit(unit_id=unit.id)
        normal_lessons = [lesson for lesson in lessons if lesson.kind == "normal"]
        review_lessons = [lesson for lesson in lessons if lesson.kind == "review_previous_units"]
        exam_lessons = [lesson for lesson in lessons if lesson.kind == "exam"]

        bootstrap_only_unit = (
            len(normal_lessons) == 1
            and unit.order_index == 1
        )
        if not bootstrap_only_unit and not (minimum_normal_lessons <= len(normal_lessons) <= maximum_normal_lessons):
            msg = (
                f"Unit {unit.id} has wrong normal lesson count: {len(normal_lessons)} not in "
                f"[{minimum_normal_lessons}, {maximum_normal_lessons}]"
            )
            raise ValueError(msg)
        if len(review_lessons) != expected_review_lessons:
            msg = (
                f"Unit {unit.id} has wrong review_previous_units lesson count: "
                f"{len(review_lessons)} != {expected_review_lessons}"
            )
            raise ValueError(msg)
        if len(exam_lessons) != expected_exam_lessons:
            msg = f"Unit {unit.id} has wrong exam lesson count: {len(exam_lessons)} != {expected_exam_lessons}"
            raise ValueError(msg)
        expected_lesson_kinds = (
            ["normal"] * len(normal_lessons)
            + ["review_previous_units"] * expected_review_lessons
            + ["exam"] * expected_exam_lessons
        )
        lesson_kinds = [lesson.kind for lesson in lessons]
        if lesson_kinds != expected_lesson_kinds:
            msg = f"Unit {unit.id} lesson kinds do not match expected bounded order: {lesson_kinds!r}"
            raise ValueError(msg)
        if lessons[-1].kind != "exam":
            msg = f"Unit {unit.id} last lesson must be exam"
            raise ValueError(msg)

        for lesson in lessons:
            item_count = q.count_items_for_lesson(lesson_id=lesson.id)
            if item_count == 0:
                msg = f"Lesson {lesson.id} has no items"
                raise ValueError(msg)
            total_item_count += item_count

        total_lesson_count += len(lessons)

    return SectionAcceptanceStats(
        section_id=section.id,
        accepted=True,
        unit_count=unit_count,
        lesson_count=total_lesson_count,
        item_count=total_item_count,
    )
