from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.runtime.runner import (
    BuildCheckpoint,
    default_checkpoint_path,
    is_checkpoint_fully_completed,
    read_checkpoint,
    resolve_next_stage_name,
    run_next_build_stage,
    write_checkpoint,
    write_checkpoint_attempt_log,
)
from domain.content.models import CourseVersion, ThemeTag
from tests.helpers.builder import load_test_config

load_config = load_test_config


def test_read_checkpoint_returns_empty_checkpoint_when_file_missing(tmp_path: Path) -> None:
    checkpoint = read_checkpoint(tmp_path / "missing.json", build_version=7, section_code="PRE_A1")

    assert checkpoint == BuildCheckpoint(
        build_version=7,
        section_code="PRE_A1",
        course_version_id=None,
        completed_stage_names=(),
        last_attempted_stage_name=None,
        last_attempt_log_lines=(),
    )


def test_write_then_read_checkpoint_round_trips(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    expected = BuildCheckpoint(
        build_version=7,
        section_code="PRE_A1",
        course_version_id="course-version-1",
        completed_stage_names=("create_course_build", "bootstrap_catalog", "pattern_vocab_generation"),
        last_attempted_stage_name="pattern_vocab_generation",
        last_attempt_log_lines=("line one", "line two"),
    )

    write_checkpoint(checkpoint_path, expected)

    assert read_checkpoint(checkpoint_path, build_version=7, section_code="PRE_A1") == expected


def test_default_checkpoint_path_uses_config_identity_and_build_version(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert default_checkpoint_path(config=config, build_version=7) == Path(
        "build_checkpoints/course_build_en-ja_v1_build7_PRE_A1.json"
    )


def test_resolve_next_stage_name_uses_checkpoint_state(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    write_checkpoint(
        checkpoint_path,
        BuildCheckpoint(
            build_version=7,
            section_code="PRE_A1",
            course_version_id="course-version-1",
            completed_stage_names=("create_course_build", "bootstrap_catalog"),
        ),
    )

    assert (
        resolve_next_stage_name(
            checkpoint_path=checkpoint_path,
            build_version=7,
            section_code="PRE_A1",
        )
        == "pattern_vocab_generation"
    )


def test_is_checkpoint_fully_completed_returns_true_only_for_full_stage_sequence(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    write_checkpoint(
        checkpoint_path,
        BuildCheckpoint(
            build_version=7,
            section_code="PRE_A1",
            course_version_id="course-version-1",
            completed_stage_names=(
                "create_course_build",
                "bootstrap_catalog",
                "pattern_vocab_generation",
                "section_curriculum_planning",
                "unit_metadata_generation",
                "plan_normal_lessons",
                "content_assembly",
                "release",
            ),
        ),
    )

    assert is_checkpoint_fully_completed(
        checkpoint_path=checkpoint_path,
        build_version=7,
        section_code="PRE_A1",
    )


def test_write_checkpoint_attempt_log_preserves_completed_stages(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    write_checkpoint(
        checkpoint_path,
        BuildCheckpoint(
            build_version=7,
            section_code="PRE_A1",
            course_version_id="course-version-1",
            completed_stage_names=("create_course_build", "bootstrap_catalog"),
        ),
    )

    write_checkpoint_attempt_log(
        checkpoint_path,
        build_version=7,
        section_code="PRE_A1",
        stage_name="pattern_vocab_generation",
        log_lines=["line one", "line two"],
    )

    assert read_checkpoint(checkpoint_path, build_version=7, section_code="PRE_A1") == BuildCheckpoint(
        build_version=7,
        section_code="PRE_A1",
        course_version_id="course-version-1",
        completed_stage_names=("create_course_build", "bootstrap_catalog"),
        last_attempted_stage_name="pattern_vocab_generation",
        last_attempt_log_lines=("line one", "line two"),
    )


def test_run_next_build_stage_creates_draft_build_as_stage_zero(db_session: Session, tmp_path: Path) -> None:
    config = load_config(tmp_path)
    checkpoint_path = tmp_path / "checkpoint.json"

    result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=3,
        checkpoint_path=checkpoint_path,
    )

    assert result.build_version == 3
    assert result.completed_stage_name == "create_course_build"
    assert result.completed_stage_index == 0
    assert result.remaining_stage_count == 7
    persisted_course_version = db_session.get(CourseVersion, result.course_version_id)
    assert persisted_course_version is not None
    assert persisted_course_version.build_version == 3
    assert read_checkpoint(checkpoint_path, build_version=3, section_code="PRE_A1") == BuildCheckpoint(
        build_version=3,
        section_code="PRE_A1",
        course_version_id=result.course_version_id,
        completed_stage_names=("create_course_build",),
    )


def test_run_next_build_stage_runs_only_one_nonzero_stage_and_updates_checkpoint(
    db_session: Session, tmp_path: Path
) -> None:
    config = load_config(tmp_path)
    checkpoint_path = tmp_path / "checkpoint.json"
    create_result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=4,
        checkpoint_path=checkpoint_path,
    )
    result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=4,
        checkpoint_path=checkpoint_path,
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
    assert read_checkpoint(checkpoint_path, build_version=4, section_code="PRE_A1").completed_stage_names == (
        "create_course_build",
        "bootstrap_catalog",
    )
    persisted_course_version = db_session.get(CourseVersion, create_result.course_version_id)
    assert persisted_course_version is not None


def test_run_next_build_stage_does_not_update_checkpoint_on_failure(db_session: Session, tmp_path: Path) -> None:
    config = load_config(tmp_path)
    checkpoint_path = tmp_path / "checkpoint.json"
    create_result = run_next_build_stage(
        db=db_session,
        config=config,
        build_version=5,
        checkpoint_path=checkpoint_path,
    )
    write_checkpoint(
        checkpoint_path,
        BuildCheckpoint(
            build_version=5,
            section_code="PRE_A1",
            course_version_id=create_result.course_version_id,
            completed_stage_names=(
                "create_course_build",
                "bootstrap_catalog",
            ),
        ),
    )

    with pytest.raises(ValueError, match="Section config must be imported before section word generation"):
        run_next_build_stage(
            db=db_session,
            config=config,
            build_version=5,
            checkpoint_path=checkpoint_path,
        )

    assert read_checkpoint(checkpoint_path, build_version=5, section_code="PRE_A1").completed_stage_names == (
        "create_course_build",
        "bootstrap_catalog",
    )
