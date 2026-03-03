from __future__ import annotations

from dataclasses import dataclass

from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from course_builder.llm.unit_metadata_generation import graph as unit_metadata_generation_graph
from course_builder.runtime.models import BuildContext
from course_builder.stages.assembly.hints_and_kanji_introductions import build_hints_and_kanji_introductions
from course_builder.stages.assembly.lesson_item_generation import generate_lesson_items
from course_builder.stages.assembly.pattern_example_sentences import persist_pattern_example_sentences
from course_builder.stages.assembly.review_exam_lesson_creation import create_algorithmic_review_exam_lessons
from course_builder.stages.assembly.tile_generation import build_tile_sets
from course_builder.stages.bootstrap.bootstrap_seed_words import insert_bootstrap_seed_words
from course_builder.stages.bootstrap.pattern_catalog import import_pattern_catalog
from course_builder.stages.bootstrap.sections import import_section_config
from course_builder.stages.bootstrap.theme_tags import import_theme_tags
from course_builder.stages.planning.normal_lesson_planning import plan_normal_lessons
from course_builder.stages.planning.section_curriculum_planning import persist_section_curriculum
from course_builder.stages.planning.unit_metadata_generation import generate_unit_metadata
from tests.helpers.fake_llms import SequentialStructuredLlm


@dataclass(frozen=True, slots=True)
class CourseBuildPipelineState:
    context: BuildContext
    unit_llm: SequentialStructuredLlm


def build_seeded_section(*, db_session: Session, context: BuildContext) -> BuildContext:
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)
    return context


def build_sentence_ready_course(
    *,
    db_session: Session,
    context: BuildContext,
    monkeypatch: MonkeyPatch,
    unit_payloads: list[dict[str, object]],
) -> CourseBuildPipelineState:
    build_seeded_section(db_session=db_session, context=context)

    unit_llm = SequentialStructuredLlm(payloads=unit_payloads)
    monkeypatch.setattr(unit_metadata_generation_graph, "create_chat_openai", lambda *, model: unit_llm)
    persist_section_curriculum(db_session, context=context)
    generate_unit_metadata(db_session, context=context)
    plan_normal_lessons(db_session, context=context)

    persist_pattern_example_sentences(db_session, context=context)
    return CourseBuildPipelineState(context=context, unit_llm=unit_llm)


def build_review_ready_course(
    *,
    db_session: Session,
    context: BuildContext,
    monkeypatch: MonkeyPatch,
    unit_payloads: list[dict[str, object]],
) -> CourseBuildPipelineState:
    state = build_sentence_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=unit_payloads,
    )
    create_algorithmic_review_exam_lessons(db_session, context=context)
    build_tile_sets(db_session, context=context)
    generate_lesson_items(db_session, context=context)
    return state


def build_publish_ready_course(
    *,
    db_session: Session,
    context: BuildContext,
    monkeypatch: MonkeyPatch,
    unit_payloads: list[dict[str, object]],
) -> CourseBuildPipelineState:
    state = build_review_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=unit_payloads,
    )
    build_hints_and_kanji_introductions(db_session, context=context)
    return state
