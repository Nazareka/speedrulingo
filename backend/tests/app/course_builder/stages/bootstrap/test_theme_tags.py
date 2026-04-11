from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext
from course_builder.stages.bootstrap.theme_tags import (
    ImportThemeTagsStep,
    ThemeTagImportStats,
    import_theme_tags,
)
from domain.content.models import ThemeTag
from tests.helpers.builder import CourseBuildTestRunner, create_test_build_context, load_test_config


def build_context(db_session: Session, tmp_path: Path, *, build_version: int = 1) -> BuildContext:
    return create_test_build_context(db_session, tmp_path, build_version=build_version)


def test_import_theme_tags_persists_theme_catalog(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)

    stats = import_theme_tags(db_session, context=context)

    assert stats == ThemeTagImportStats(theme_tags_created=2)
    persisted_codes = db_session.scalars(
        select(ThemeTag.code).where(ThemeTag.course_version_id == context.course_version_id).order_by(ThemeTag.code)
    ).all()
    assert persisted_codes == ["THEME_HOME_PLACE", "THEME_SELF_INTRO"]


def test_import_theme_tags_step_is_idempotent_for_same_course_version(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)
    step = ImportThemeTagsStep()

    first_stats = step.run(db=db_session, context=context)
    second_stats = step.run(db=db_session, context=context)

    assert first_stats.theme_tags_created == 2
    assert second_stats.theme_tags_created == 0


def test_import_theme_tags_step_rejects_conflicting_existing_definition_in_same_course_version(
    db_session: Session, tmp_path: Path
) -> None:
    context = build_context(db_session, tmp_path)
    db_session.add(
        ThemeTag(
            course_version_id=context.course_version_id,
            code="THEME_SELF_INTRO",
            name="Wrong",
        )
    )
    db_session.commit()

    with pytest.raises(ValueError, match="Theme tag definition conflict"):
        ImportThemeTagsStep().run(db=db_session, context=context)


def test_import_theme_tags_creates_separate_rows_for_different_course_versions(
    db_session: Session, tmp_path: Path
) -> None:
    first_context = build_context(db_session, tmp_path, build_version=1)
    second_context = build_context(db_session, tmp_path, build_version=2)

    first_stats = ImportThemeTagsStep().run(db=db_session, context=first_context)
    second_stats = ImportThemeTagsStep().run(db=db_session, context=second_context)

    assert first_stats.theme_tags_created == 2
    assert second_stats.theme_tags_created == 2
    assert db_session.scalar(select(func.count()).select_from(ThemeTag)) == 4


def test_test_runner_runs_theme_tag_import(db_session: Session, tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    runner = CourseBuildTestRunner(steps=[ImportThemeTagsStep()])

    context = runner.run(db=db_session, config=config)

    persisted_codes = db_session.scalars(
        select(ThemeTag.code).where(ThemeTag.course_version_id == context.course_version_id).order_by(ThemeTag.code)
    ).all()
    assert persisted_codes == ["THEME_HOME_PLACE", "THEME_SELF_INTRO"]
