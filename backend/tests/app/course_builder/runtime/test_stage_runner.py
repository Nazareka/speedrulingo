from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.runtime.runner import (
    BuildCheckpoint,
    is_checkpoint_fully_completed,
    read_checkpoint,
    resolve_next_stage_name,
    run_next_build_stage,
    write_checkpoint,
)
from domain.content.models import CourseVersion, ThemeTag
from tests.helpers.builder import load_test_config

load_config = load_test_config


def test_read_checkpoint_returns_empty_checkpoint_when_row_missing(db_session: Session) -> None:
    checkpoint = read_checkpoint(db_session, build_version=7, section_code="PRE_A1")

    assert checkpoint == BuildCheckpoint(
        build_version=7,
        section_code="PRE_A1",
        course_version_id=None,
        next_stage_index=0,
        last_attempted_stage_name=None,
    )


def test_write_then_read_checkpoint_round_trips(db_session: Session) -> None:
    expected = BuildCheckpoint(
        build_version=7,
        section_code="PRE_A1",
        course_version_id=None,
        next_stage_index=3,
        last_attempted_stage_name="pattern_vocab_generation",
    )

    write_checkpoint(db_session, expected)

    assert read_checkpoint(db_session, build_version=7, section_code="PRE_A1") == expected


def test_resolve_next_stage_name_uses_checkpoint_state(db_session: Session) -> None:
    write_checkpoint(
        db_session,
        BuildCheckpoint(
            build_version=7,
            section_code="PRE_A1",
            course_version_id=None,
            next_stage_index=2,
        ),
    )

    assert (
        resolve_next_stage_name(
            db=db_session,
            build_version=7,
            section_code="PRE_A1",
        )
        == "pattern_vocab_generation"
    )


def test_is_checkpoint_fully_completed_returns_true_only_for_full_stage_sequence(db_session: Session) -> None:
    write_checkpoint(
        db_session,
        BuildCheckpoint(
            build_version=7,
            section_code="PRE_A1",
            course_version_id=None,
            next_stage_index=8,
        ),
    )

    assert is_checkpoint_fully_completed(
        db=db_session,
        build_version=7,
        section_code="PRE_A1",
    )


def test_run_next_build_stage_creates_draft_build_as_stage_zero(db_session: Session, tmp_path: Path) -> None:
    config = load_config(tmp_path)

    result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=3,
    )

    assert result.build_version == 3
    assert result.completed_stage_name == "create_course_build"
    assert result.completed_stage_index == 0
    assert result.remaining_stage_count == 7
    persisted_course_version = db_session.get(CourseVersion, result.course_version_id)
    assert persisted_course_version is not None
    assert persisted_course_version.build_version == 3
    assert read_checkpoint(db_session, build_version=3, section_code="PRE_A1") == BuildCheckpoint(
        build_version=3,
        section_code="PRE_A1",
        course_version_id=result.course_version_id,
        next_stage_index=1,
        last_attempted_stage_name="create_course_build",
    )


def test_run_next_build_stage_runs_only_one_nonzero_stage_and_updates_checkpoint(
    db_session: Session, tmp_path: Path
) -> None:
    config = load_config(tmp_path)
    create_result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=4,
    )
    result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=4,
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
    assert read_checkpoint(db_session, build_version=4, section_code="PRE_A1") == BuildCheckpoint(
        build_version=4,
        section_code="PRE_A1",
        course_version_id=create_result.course_version_id,
        next_stage_index=2,
        last_attempted_stage_name="bootstrap_catalog",
    )
    persisted_course_version = db_session.get(CourseVersion, create_result.course_version_id)
    assert persisted_course_version is not None


def test_run_next_build_stage_does_not_update_checkpoint_on_failure(db_session: Session, tmp_path: Path) -> None:
    config = load_config(tmp_path)
    create_result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=5,
    )
    write_checkpoint(
        db_session,
        BuildCheckpoint(
            build_version=5,
            section_code="PRE_A1",
            course_version_id=create_result.course_version_id,
            next_stage_index=2,
        ),
    )
    db_session.commit()

    with pytest.raises(ValueError, match="Section config must be imported before section word generation"):
        run_next_build_stage(
            db=db_session,
            config=config,
            build_version=5,
        )

    assert read_checkpoint(db_session, build_version=5, section_code="PRE_A1") == BuildCheckpoint(
        build_version=5,
        section_code="PRE_A1",
        course_version_id=create_result.course_version_id,
        next_stage_index=2,
        last_attempted_stage_name=None,
    )
