from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from course_builder.engine.orchestration import read_declared_section_codes, run_build_stage_with_attempt_log
from course_builder.engine.runner import BuildStageRunResult
from tests.helpers.builder import load_test_config


def test_read_declared_section_codes_returns_ordered_section_codes(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "course.yaml").write_text("sections:\n  - PRE_A1\n  - A1_1\n", encoding="utf-8")

    assert read_declared_section_codes(config_root) == ["PRE_A1", "A1_1"]


def test_run_build_stage_with_attempt_log_forwards_extra_logs(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    tmp_path: Path,
) -> None:
    config = load_test_config(tmp_path)
    extra_messages: list[str] = []

    def fake_run_next_build_stage(**_: object) -> BuildStageRunResult:
        logging.getLogger("test.course_builder").warning("stage log line")
        return BuildStageRunResult(
            build_version=9,
            course_version_id="course-version-1",
            completed_stage_name="bootstrap_catalog",
            completed_stage_index=1,
            remaining_stage_count=6,
        )

    class ExtraHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            extra_messages.append(record.getMessage())

    monkeypatch.setattr("course_builder.engine.orchestration.run_next_build_stage", fake_run_next_build_stage)

    result = run_build_stage_with_attempt_log(
        db=db_session,
        config=config,
        build_version=9,
        build_run_id="build-run-1",
        extra_root_handler=ExtraHandler(),
    )

    assert result.completed_stage_name == "bootstrap_catalog"
    assert extra_messages == ["stage log line"]
