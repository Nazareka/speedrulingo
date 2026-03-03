from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.stages.bootstrap.pattern_catalog import (
    ImportPatternCatalogStep,
    PatternCatalogImportStats,
    import_pattern_catalog,
)
from domain.content.models import Pattern
from tests.helpers.builder import CourseBuildTestRunner, create_test_build_context, load_test_config


def test_import_pattern_catalog_persists_ordered_rows(db_session: Session, tmp_path: Path) -> None:
    context = create_test_build_context(db_session, tmp_path)

    stats = import_pattern_catalog(db_session, context=context)

    assert stats == PatternCatalogImportStats(patterns_created=1)
    persisted = db_session.scalars(
        select(Pattern).where(Pattern.course_version_id == context.course_version_id).order_by(Pattern.intro_order)
    ).all()
    assert len(persisted) == 1
    assert persisted[0].code == "WA_DESU_STATEMENT"
    assert persisted[0].intro_order == 1
    assert persisted[0].is_bootstrap is True


def test_import_pattern_catalog_step_rejects_duplicate_import(db_session: Session, tmp_path: Path) -> None:
    context = create_test_build_context(db_session, tmp_path)
    step = ImportPatternCatalogStep()

    first_stats = step.run(db=db_session, context=context)

    assert first_stats.patterns_created == 1
    with pytest.raises(ValueError, match="Pattern catalog already exists"):
        step.run(db=db_session, context=context)


def test_test_runner_runs_pattern_catalog_step(db_session: Session, tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    runner = CourseBuildTestRunner(steps=[ImportPatternCatalogStep()])

    context = runner.run(db=db_session, config=config)

    persisted_codes = db_session.scalars(
        select(Pattern.code).where(Pattern.course_version_id == context.course_version_id).order_by(Pattern.intro_order)
    ).all()
    assert persisted_codes == ["WA_DESU_STATEMENT"]
