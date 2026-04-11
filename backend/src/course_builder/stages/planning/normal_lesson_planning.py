from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.queries.planning import PlanningQueries
from course_builder.stages.planning.section_curriculum import load_section_curriculum
from domain.content.models import (
    Lesson,
    LessonPatternLink,
    LessonWord,
)


@dataclass(frozen=True, slots=True)
class NormalLessonPlanningStats:
    lessons_created: int
    lesson_words_created: int
    lesson_pattern_links_created: int
    iterations: int


def plan_normal_lessons(
    db: Session,
    *,
    context: BuildContext,
) -> NormalLessonPlanningStats:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    section = q.get_section()
    if section is None:
        msg = (
            f"Section config must exist before normal lesson planning for course_version_id={context.course_version_id}"
        )
        raise ValueError(msg)

    units = q.list_units_for_section(section_id=section.id)
    if not units:
        msg = f"Units must exist before normal lesson planning for course_version_id={context.course_version_id}"
        raise ValueError(msg)
    if q.exists_normal_lessons_for_section(section_id=section.id):
        msg = f"Normal lessons already exist for course_version_id={context.course_version_id}"
        raise ValueError(msg)

    words = q.list_curriculum_words()
    section_curriculum = load_section_curriculum(context=context, q=q)

    unit_by_order = {unit.order_index: unit for unit in units}
    word_id_by_lemma = {word.canonical_writing_ja: word.word_id for word in words}
    pattern_id_by_code = q.map_pattern_id_by_code()

    lessons_created = 0
    lesson_words_created = 0
    lesson_pattern_links_created = 0

    for planned_unit in section_curriculum.units:
        unit = unit_by_order[planned_unit.order_index]
        for planned_lesson in planned_unit.lessons:
            lesson = Lesson(
                unit_id=unit.id,
                order_index=planned_lesson.lesson_index_within_unit,
                kind="normal",
                force_kana_display=planned_lesson.force_kana_display,
                target_item_count=planned_lesson.target_item_count,
            )
            db.add(lesson)
            db.flush()
            lessons_created += 1

            target_word_set = set(planned_lesson.target_word_lemmas)
            for lemma in planned_lesson.available_word_lemmas:
                db.add(
                    LessonWord(
                        lesson_id=lesson.id,
                        word_id=word_id_by_lemma[lemma],
                        role="new" if lemma in target_word_set else "review",
                    )
                )
                lesson_words_created += 1

            target_pattern_codes = set(planned_lesson.target_pattern_codes)
            for code in planned_lesson.available_pattern_codes:
                db.add(
                    LessonPatternLink(
                        lesson_id=lesson.id,
                        pattern_id=pattern_id_by_code[code],
                        role="introduce" if code in target_pattern_codes else "review",
                    )
                )
                lesson_pattern_links_created += 1

    db.commit()
    return NormalLessonPlanningStats(
        lessons_created=lessons_created,
        lesson_words_created=lesson_words_created,
        lesson_pattern_links_created=lesson_pattern_links_created,
        iterations=1,
    )


class NormalLessonPlanningStage(BuildStep):
    name = "plan_normal_lessons"

    @override
    def run(self, *, db: Session, context: BuildContext) -> NormalLessonPlanningStats:
        return plan_normal_lessons(db, context=context)
