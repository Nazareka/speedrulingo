from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from course_builder.llm.unit_metadata_generation import graph as unit_metadata_generation_graph
from course_builder.stages.bootstrap.bootstrap_seed_words import insert_bootstrap_seed_words
from course_builder.stages.bootstrap.pattern_catalog import import_pattern_catalog
from course_builder.stages.bootstrap.sections import import_section_config
from course_builder.stages.bootstrap.theme_tags import import_theme_tags
from course_builder.stages.planning.normal_lesson_planning import plan_normal_lessons
from course_builder.stages.planning.section_curriculum_planning import persist_section_curriculum
from course_builder.stages.planning.unit_metadata_generation import generate_unit_metadata
from domain.content.models import Lesson, LessonWord, Unit
from tests.helpers.builder import create_test_build_context
from tests.helpers.fake_llms import SequentialStructuredLlm
from tests.helpers.scenarios import single_intro_unit_plan_payload
from tests.helpers.test_config_source import TEST_CONFIG_YAML


def unit_test_config() -> str:
    return TEST_CONFIG_YAML


FakeStructuredLlm = SequentialStructuredLlm


def test_plan_normal_lessons_persists_normal_lessons_for_all_units(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path, content=unit_test_config())
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)

    unit_llm = FakeStructuredLlm(payloads=[single_intro_unit_plan_payload()])
    monkeypatch.setattr(
        unit_metadata_generation_graph,
        "create_chat_openai",
        lambda *, model, reasoning_effort: unit_llm,
    )
    persist_section_curriculum(db_session, context=context)
    generate_unit_metadata(db_session, context=context)

    stats = plan_normal_lessons(db_session, context=context)

    assert stats.lessons_created >= 2
    assert stats.iterations == 1
    assert stats.lesson_words_created >= 1
    assert stats.lesson_pattern_links_created >= 1
    persisted_lessons = db_session.scalars(select(Lesson).order_by(Lesson.order_index)).all()
    assert len(persisted_lessons) == stats.lessons_created
    persisted_units = db_session.scalars(select(Unit).order_by(Unit.order_index)).all()
    assert [unit.title for unit in persisted_units] == ["Section 1 Unit 1"]
    safe_allowed_counts = db_session.execute(
        select(Lesson.id, func.count())
        .join(LessonWord, LessonWord.lesson_id == Lesson.id)
        .where(LessonWord.role == "safe_allowed")
        .group_by(Lesson.id)
        .order_by(Lesson.id)
    ).all()
    assert safe_allowed_counts == []
