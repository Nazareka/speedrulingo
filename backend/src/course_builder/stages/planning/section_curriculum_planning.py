from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.queries.planning import (
    CurriculumPatternExample,
    PlanningQueries,
)
from course_builder.stages.planning.section_curriculum import build_section_curriculum
from domain.content.models import PlannedLesson, PlannedUnit


@dataclass(frozen=True, slots=True)
class SectionCurriculumPlanningStats:
    planned_units_created: int
    planned_lessons_created: int
    iterations: int


def _serialize_pattern_examples(
    examples: tuple[CurriculumPatternExample, ...],
) -> list[dict[str, object]]:
    return [
        {
            "pattern_code": example.pattern_code,
            "ja_text": example.ja_text,
            "en_text": example.en_text,
            "lexicon_used": [list(lexeme) for lexeme in example.lexicon_used],
        }
        for example in examples
    ]


def persist_section_curriculum(
    db: Session,
    *,
    context: BuildContext,
) -> SectionCurriculumPlanningStats:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    if q.exists_planned_units():
        msg = (
            f"Planned section curriculum already exists for course_version_id={context.course_version_id} "
            f"section_code={context.section_code}"
        )
        raise ValueError(msg)
    section_id = q.get_section_id()
    if section_id is None:
        msg = f"Section config must be imported before curriculum planning for section_code={context.section_code}"
        raise ValueError(msg)

    section_curriculum = build_section_curriculum(
        config=context.config,
        words=q.list_curriculum_words(),
        patterns=q.list_curriculum_patterns(context=context),
        previously_introduced_word_lemmas=q.list_previously_introduced_word_lemmas(),
        previously_introduced_pattern_codes=q.list_previously_introduced_pattern_codes(),
        current_section_bootstrap_expression_lemmas=q.list_current_section_bootstrap_expression_lemmas(),
        generated_sentence_count_by_lemma=q.map_generated_sentence_count_by_target_lemma_for_section(),
    )
    planned_units_created = 0
    planned_lessons_created = 0
    for planned_unit in section_curriculum.units:
        planned_unit_row = PlannedUnit(
            section_id=section_id,
            order_index=planned_unit.order_index,
            primary_theme_codes=list(planned_unit.primary_theme_codes),
            pattern_codes=list(planned_unit.pattern_codes),
        )
        db.add(planned_unit_row)
        db.flush()
        planned_units_created += 1
        for planned_lesson in planned_unit.lessons:
            db.add(
                PlannedLesson(
                    planned_unit_id=planned_unit_row.id,
                    order_index=planned_lesson.lesson_index_within_unit,
                    kind=planned_lesson.lesson_kind,
                    force_kana_display=planned_lesson.force_kana_display,
                    target_item_count=planned_lesson.target_item_count,
                    introduced_word_lemmas=list(planned_lesson.introduced_word_lemmas),
                    kanji_focus_word_lemmas=list(planned_lesson.kanji_focus_word_lemmas),
                    target_word_lemmas=list(planned_lesson.target_word_lemmas),
                    target_pattern_codes=list(planned_lesson.target_pattern_codes),
                    target_pattern_code=planned_lesson.target_pattern_code,
                    target_pattern_examples=_serialize_pattern_examples(planned_lesson.target_pattern_examples),
                    available_word_lemmas=list(planned_lesson.available_word_lemmas),
                    available_pattern_codes=list(planned_lesson.available_pattern_codes),
                    target_pattern_sentence_count=planned_lesson.target_pattern_sentence_count,
                )
            )
            planned_lessons_created += 1

    section = q.get_section()
    if section is not None:
        section.target_new_word_count = len(
            {
                lemma
                for planned_unit in section_curriculum.units
                for planned_lesson in planned_unit.lessons
                for lemma in planned_lesson.introduced_word_lemmas
            }
        )
    db.commit()
    return SectionCurriculumPlanningStats(
        planned_units_created=planned_units_created,
        planned_lessons_created=planned_lessons_created,
        iterations=1 if planned_lessons_created > 0 else 0,
    )


class SectionCurriculumPlanningStage(BuildStep):
    name = "section_curriculum_planning"

    @override
    def run(self, *, db: Session, context: BuildContext) -> SectionCurriculumPlanningStats:
        return persist_section_curriculum(db, context=context)
