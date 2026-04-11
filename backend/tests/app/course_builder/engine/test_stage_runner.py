from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.engine.runner import (
    BuildProgressSnapshot,
    is_build_progress_fully_completed,
    is_section_build_fully_completed,
    read_build_progress,
    resolve_next_stage_name,
    run_next_build_stage,
)
from domain.content.models import CourseBuildRun, CourseBuildStageRun, CourseVersion, ThemeTag
from tests.helpers.builder import load_test_config

load_config = load_test_config
COURSE_VERSION_ID = "11111111-1111-1111-1111-111111111111"


def _insert_course_version(db_session: Session, *, build_version: int) -> None:
    db_session.add(
        CourseVersion(
            id=COURSE_VERSION_ID,
            code="en-ja",
            version=1,
            build_version=build_version,
            status="draft",
            config_version="v1",
            config_hash="hash",
        )
    )
    db_session.flush()


def _insert_build_run(
    db_session: Session,
    *,
    build_version: int,
    section_code: str,
    course_version_id: str | None = None,
) -> str:
    build_run = CourseBuildRun(
        workflow_id="workflow-1",
        build_version=build_version,
        config_path="config/en-ja-v1",
        scope_kind="section",
        section_code=section_code,
        status="running",
        all_stages=True,
        total_stage_count=8,
        course_version_id=course_version_id,
    )
    db_session.add(build_run)
    db_session.flush()
    return build_run.id


def _insert_stage_run(
    db_session: Session,
    *,
    build_run_id: str,
    section_code: str,
    stage_name: str,
    stage_index: int,
    status: str,
) -> None:
    db_session.add(
        CourseBuildStageRun(
            build_run_id=build_run_id,
            section_code=section_code,
            stage_name=stage_name,
            stage_index=stage_index,
            status=status,
        )
    )
    db_session.flush()


def test_read_build_progress_returns_empty_snapshot_when_no_stage_history(db_session: Session) -> None:
    build_run_id = _insert_build_run(db_session, build_version=7, section_code="PRE_A1")

    progress = read_build_progress(db_session, build_run_id=build_run_id)

    assert progress == BuildProgressSnapshot(
        build_run_id=build_run_id,
        build_version=7,
        section_code="PRE_A1",
        course_version_id=None,
        next_stage_index=0,
        last_attempted_stage_name=None,
    )


def test_read_build_progress_derives_progress_from_completed_stage_runs(db_session: Session) -> None:
    _insert_course_version(db_session, build_version=7)
    build_run_id = _insert_build_run(
        db_session,
        build_version=7,
        section_code="PRE_A1",
        course_version_id=COURSE_VERSION_ID,
    )
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="create_course_build",
        stage_index=0,
        status="completed",
    )
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="bootstrap_catalog",
        stage_index=1,
        status="completed",
    )
    db_session.commit()

    assert read_build_progress(db_session, build_run_id=build_run_id) == BuildProgressSnapshot(
        build_run_id=build_run_id,
        build_version=7,
        section_code="PRE_A1",
        course_version_id=COURSE_VERSION_ID,
        next_stage_index=2,
        last_attempted_stage_name="bootstrap_catalog",
    )


def test_resolve_next_stage_name_uses_derived_progress(db_session: Session) -> None:
    build_run_id = _insert_build_run(db_session, build_version=7, section_code="PRE_A1")
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="create_course_build",
        stage_index=0,
        status="completed",
    )
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="bootstrap_catalog",
        stage_index=1,
        status="completed",
    )
    db_session.commit()

    assert (
        resolve_next_stage_name(
            db=db_session,
            build_run_id=build_run_id,
        )
        == "pattern_vocab_generation"
    )


def test_read_build_progress_rejects_stage_registry_name_mismatch(db_session: Session) -> None:
    build_run_id = _insert_build_run(db_session, build_version=7, section_code="PRE_A1")
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="wrong_stage_name",
        stage_index=1,
        status="completed",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="Build stage registry changed"):
        read_build_progress(db_session, build_run_id=build_run_id)


def test_is_build_progress_fully_completed_uses_completed_stage_runs(db_session: Session) -> None:
    build_run_id = _insert_build_run(db_session, build_version=7, section_code="PRE_A1")
    for stage_index, stage_name in enumerate(
        [
            "create_course_build",
            "bootstrap_catalog",
            "pattern_vocab_generation",
            "section_curriculum_planning",
            "unit_metadata_generation",
            "plan_normal_lessons",
            "content_assembly",
            "release",
        ]
    ):
        _insert_stage_run(
            db_session,
            build_run_id=build_run_id,
            section_code="PRE_A1",
            stage_name=stage_name,
            stage_index=stage_index,
            status="completed",
        )

    assert is_build_progress_fully_completed(
        db=db_session,
        build_run_id=build_run_id,
    )


def test_run_next_build_stage_creates_draft_build_as_stage_zero(db_session: Session, tmp_path: Path) -> None:
    config = load_config(tmp_path)
    build_run_id = _insert_build_run(db_session, build_version=3, section_code="PRE_A1")

    result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=3,
        build_run_id=build_run_id,
    )

    assert result.build_version == 3
    assert result.completed_stage_name == "create_course_build"
    assert result.completed_stage_index == 0
    assert result.remaining_stage_count == 7
    persisted_course_version = db_session.get(CourseVersion, result.course_version_id)
    assert persisted_course_version is not None
    assert persisted_course_version.build_version == 3


def test_run_next_build_stage_runs_only_one_nonzero_stage_with_stage_history(
    db_session: Session, tmp_path: Path
) -> None:
    config = load_config(tmp_path)
    initial_build_run_id = _insert_build_run(db_session, build_version=4, section_code="PRE_A1")
    create_result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=4,
        build_run_id=initial_build_run_id,
    )
    build_run_id = _insert_build_run(
        db_session,
        build_version=4,
        section_code="PRE_A1",
        course_version_id=create_result.course_version_id,
    )
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="create_course_build",
        stage_index=0,
        status="completed",
    )
    db_session.commit()

    result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=4,
        build_run_id=build_run_id,
    )

    assert result.completed_stage_name == "bootstrap_catalog"
    assert result.completed_stage_index == 1
    assert result.remaining_stage_count == 6
    assert list(
        db_session.scalars(
            select(ThemeTag.code)
            .where(ThemeTag.course_version_id == create_result.course_version_id)
            .order_by(ThemeTag.code)
        )
    ) == [
        "THEME_HOME_PLACE",
        "THEME_SELF_INTRO",
    ]
    persisted_course_version = db_session.get(CourseVersion, create_result.course_version_id)
    assert persisted_course_version is not None


def test_run_next_build_stage_keeps_derived_progress_on_failure(db_session: Session, tmp_path: Path) -> None:
    config = load_config(tmp_path)
    initial_build_run_id = _insert_build_run(db_session, build_version=5, section_code="PRE_A1")
    create_result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=5,
        build_run_id=initial_build_run_id,
    )
    build_run_id = _insert_build_run(
        db_session,
        build_version=5,
        section_code="PRE_A1",
        course_version_id=create_result.course_version_id,
    )
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="create_course_build",
        stage_index=0,
        status="completed",
    )
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="bootstrap_catalog",
        stage_index=1,
        status="completed",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="Section config must be imported before section word generation"):
        run_next_build_stage(
            db=db_session,
            config=config,
            build_version=5,
            build_run_id=build_run_id,
        )

    assert read_build_progress(db_session, build_run_id=build_run_id) == BuildProgressSnapshot(
        build_run_id=build_run_id,
        build_version=5,
        section_code="PRE_A1",
        course_version_id=create_result.course_version_id,
        next_stage_index=2,
        last_attempted_stage_name="bootstrap_catalog",
    )


def test_is_section_build_fully_completed_uses_config_scoped_latest_run(db_session: Session) -> None:
    build_run_id = _insert_build_run(db_session, build_version=7, section_code="PRE_A1")
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="create_course_build",
        stage_index=0,
        status="completed",
    )
    _insert_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="bootstrap_catalog",
        stage_index=1,
        status="completed",
    )
    db_session.commit()

    assert not is_section_build_fully_completed(
        db=db_session,
        build_version=7,
        config_path="other-config",
        section_code="PRE_A1",
    )
    assert not is_section_build_fully_completed(
        db=db_session,
        build_version=7,
        config_path="config/en-ja-v1",
        section_code="PRE_A1",
    )
