from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.llm.unit_metadata_generation import (
    PreparedUnitInput,
    PreparedUnitLessonInput,
    PreparedUnitMetadataInput,
    run_unit_metadata_generation,
)
from course_builder.queries.planning import CurriculumUnit, PlanningQueries
from course_builder.stages.planning.section_curriculum import load_section_curriculum
from domain.content.models import (
    Unit,
    UnitPatternLink,
    UnitThemeLink,
    UnitWord,
)


@dataclass(frozen=True, slots=True)
class UnitMetadataGenerationStats:
    units_created: int
    unit_theme_links_created: int
    unit_pattern_links_created: int
    unit_words_created: int
    iterations: int


def _build_word_prompt_info_by_lemma(*, q: PlanningQueries) -> dict[str, ExistingWordPromptInfo]:
    return q.map_prompt_word_line_inputs_by_lemma()


def _build_pattern_templates_by_code(*, context: BuildContext) -> dict[str, list[str]]:
    return {pattern.code: list(pattern.templates) for pattern in context.config.patterns}


def _build_prepared_unit_input(
    *,
    planned_unit: CurriculumUnit,
) -> PreparedUnitInput:
    return PreparedUnitInput(
        order_index=planned_unit.order_index,
        lessons=[
            PreparedUnitLessonInput(
                lesson_index=lesson.lesson_index_within_unit,
                lesson_kind=lesson.lesson_kind,
                target_item_count=lesson.target_item_count,
                target_word_lemmas=list(lesson.target_word_lemmas),
                target_pattern_code=lesson.target_pattern_code,
                available_word_lemmas=list(lesson.available_word_lemmas),
                available_pattern_codes=list(lesson.available_pattern_codes),
            )
            for lesson in planned_unit.lessons
        ],
    )


def generate_unit_metadata(
    db: Session,
    *,
    context: BuildContext,
) -> UnitMetadataGenerationStats:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    section = q.get_section()
    if section is None:
        msg = f"Section config must be imported before unit planning for course_version_id={context.course_version_id}"
        raise ValueError(msg)
    if q.exists_units_for_section(section_id=section.id):
        msg = f"Units already exist for course_version_id={context.course_version_id}"
        raise ValueError(msg)

    section_curriculum = load_section_curriculum(context=context, q=q)
    words = q.list_curriculum_words()
    word_prompt_info_by_lemma = _build_word_prompt_info_by_lemma(q=q)
    pattern_templates_by_code = _build_pattern_templates_by_code(context=context)
    prepared_input = PreparedUnitMetadataInput(
        section_title=context.config.current_section.title,
        section_generation_description=context.config.current_section.generation_description,
        section_theme_codes=[
            *context.config.current_section.primary_themes,
            *context.config.current_section.secondary_themes,
        ],
        word_prompt_info_by_lemma=word_prompt_info_by_lemma,
        pattern_templates_by_code=pattern_templates_by_code,
        units=[_build_prepared_unit_input(planned_unit=planned_unit) for planned_unit in section_curriculum.units],
    )
    with asyncio.Runner() as runner:
        generation_result = runner.run(
            run_unit_metadata_generation(config=context.config, prepared_input=prepared_input)
        )
    if len(generation_result.metadata_items) != len(section_curriculum.units):
        msg = "Unit metadata generation returned a different unit count than the deterministic course plan"
        raise ValueError(msg)

    theme_code_to_id = q.map_theme_tag_id_by_code()
    pattern_id_by_code = q.map_pattern_id_by_code()
    word_id_by_lemma = {word.canonical_writing_ja: word.word_id for word in words}

    unit_theme_links_created = 0
    unit_pattern_links_created = 0
    unit_words_created = 0
    for planned_unit, unit_metadata in zip(section_curriculum.units, generation_result.metadata_items, strict=True):
        unit = Unit(
            section_id=section.id,
            order_index=planned_unit.order_index,
            title=unit_metadata.title,
            description=unit_metadata.description,
        )
        db.add(unit)
        db.flush()

        for theme_code in unit_metadata.theme_codes:
            db.add(UnitThemeLink(unit_id=unit.id, theme_tag_id=theme_code_to_id[theme_code]))
            unit_theme_links_created += 1
        for fallback_theme_code in planned_unit.primary_theme_codes:
            if fallback_theme_code in unit_metadata.theme_codes:
                continue
            db.add(UnitThemeLink(unit_id=unit.id, theme_tag_id=theme_code_to_id[fallback_theme_code]))
            unit_theme_links_created += 1

        unit_word_roles: dict[str, str] = {}
        for lesson in planned_unit.lessons:
            for lemma in lesson.available_word_lemmas:
                unit_word_roles.setdefault(lemma, "review")
            for lemma in lesson.introduced_word_lemmas:
                unit_word_roles[lemma] = "new"

        for lemma, role in unit_word_roles.items():
            db.add(UnitWord(unit_id=unit.id, word_id=word_id_by_lemma[lemma], role=role))
            unit_words_created += 1

        unit_pattern_roles: dict[str, str] = {}
        for lesson in planned_unit.lessons:
            for code in lesson.available_pattern_codes:
                unit_pattern_roles.setdefault(code, "review")
            for code in lesson.target_pattern_codes:
                unit_pattern_roles[code] = "introduce"
        for code, role in unit_pattern_roles.items():
            db.add(UnitPatternLink(unit_id=unit.id, pattern_id=pattern_id_by_code[code], role=role))
            unit_pattern_links_created += 1

    section.target_unit_count = len(section_curriculum.units)
    db.commit()
    return UnitMetadataGenerationStats(
        units_created=len(section_curriculum.units),
        unit_theme_links_created=unit_theme_links_created,
        unit_pattern_links_created=unit_pattern_links_created,
        unit_words_created=unit_words_created,
        iterations=generation_result.iterations,
    )


class UnitMetadataGenerationStage(BuildStep):
    name = "unit_metadata_generation"

    @override
    def run(self, *, db: Session, context: BuildContext) -> UnitMetadataGenerationStats:
        return generate_unit_metadata(db, context=context)
