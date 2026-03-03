from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.stages.bootstrap.pattern_catalog import ImportPatternCatalogStep, import_pattern_catalog
from course_builder.stages.bootstrap.sections import (
    ImportSectionConfigStep,
    SectionImportStats,
    import_section_config,
)
from course_builder.stages.bootstrap.theme_tags import ImportThemeTagsStep, import_theme_tags
from domain.content.models import Section, SectionPatternLink, SectionThemeLink, ThemeTag
from tests.helpers.builder import CourseBuildTestRunner, create_test_build_context, load_test_config

build_context = create_test_build_context


def test_import_section_config_persists_section_and_links(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)

    stats = import_section_config(db_session, context=context)

    assert stats == SectionImportStats(
        sections_created=1,
        section_theme_links_created=2,
        section_pattern_links_created=1,
    )
    persisted_section = db_session.scalar(
        select(Section).where(Section.course_version_id == context.course_version_id, Section.order_index == 1)
    )
    assert persisted_section is not None
    assert persisted_section.title == "Section 1"
    assert persisted_section.target_unit_count == 0
    assert persisted_section.target_new_word_count == 0

    theme_codes = db_session.scalars(
        select(ThemeTag.code).where(ThemeTag.course_version_id == context.course_version_id).order_by(ThemeTag.code)
    ).all()
    assert theme_codes == ["THEME_HOME_PLACE", "THEME_SELF_INTRO"]

    section_theme_links = db_session.scalars(
        select(SectionThemeLink.theme_tag_id).where(SectionThemeLink.section_id == persisted_section.id)
    ).all()
    assert len(section_theme_links) == 2

    section_pattern_links = db_session.scalars(
        select(SectionPatternLink.role).where(SectionPatternLink.section_id == persisted_section.id)
    ).all()
    assert section_pattern_links == ["introduce"]


def test_import_section_config_requires_pattern_catalog(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)
    import_theme_tags(db_session, context=context)

    with pytest.raises(ValueError, match="Pattern catalog must be imported before section config"):
        ImportSectionConfigStep().run(db=db_session, context=context)


def test_import_section_config_step_rejects_duplicate_import(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    step = ImportSectionConfigStep()

    first_stats = step.run(db=db_session, context=context)

    assert first_stats.sections_created == 1
    with pytest.raises(ValueError, match="Section config already exists"):
        step.run(db=db_session, context=context)


def test_import_section_config_requires_theme_tags(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)
    import_pattern_catalog(db_session, context=context)

    with pytest.raises(ValueError, match="Theme tags must be imported before section config"):
        ImportSectionConfigStep().run(db=db_session, context=context)


def test_test_runner_runs_section_import_after_pattern_import(db_session: Session, tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    runner = CourseBuildTestRunner(
        steps=[
            ImportThemeTagsStep(),
            ImportPatternCatalogStep(),
            ImportSectionConfigStep(),
        ]
    )

    context = runner.run(db=db_session, config=config)

    persisted_section_titles = db_session.scalars(
        select(Section.title).where(Section.course_version_id == context.course_version_id)
    ).all()
    assert persisted_section_titles == ["Section 1"]
