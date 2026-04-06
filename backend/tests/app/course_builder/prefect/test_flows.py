from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import Mock

import pytest

from course_builder.prefect.flows import BuildRequest, PrefectLogBridgeHandler, _run_section_build
from course_builder.runtime.runner import BuildCheckpoint, BuildStageRunResult


def test_build_section_flow_returns_stage_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stage_results = [
        BuildStageRunResult(
            build_version=12,
            course_version_id="course-version-1",
            completed_stage_name="create_course_build",
            completed_stage_index=0,
            remaining_stage_count=7,
        ),
        BuildStageRunResult(
            build_version=12,
            course_version_id="course-version-1",
            completed_stage_name="bootstrap_catalog",
            completed_stage_index=1,
            remaining_stage_count=6,
        ),
    ]
    checkpoints = [
        BuildCheckpoint(
            build_version=12,
            section_code="PRE_A1",
            course_version_id=None,
            next_stage_index=0,
        ),
        BuildCheckpoint(
            build_version=12,
            section_code="PRE_A1",
            course_version_id="course-version-1",
            next_stage_index=1,
        ),
        BuildCheckpoint(
            build_version=12,
            section_code="PRE_A1",
            course_version_id="course-version-1",
            next_stage_index=2,
        ),
    ]

    def fake_load_config_for_step_runner(config_path: Path, *, section_code: str) -> object:
        class Config:
            current_section_code = section_code

        assert config_path == tmp_path / "config"
        return Config()

    def fake_read_checkpoint(db: object, *, build_version: int, section_code: str) -> BuildCheckpoint:
        assert build_version == 12
        assert section_code == "PRE_A1"
        return checkpoints.pop(0)

    def fake_run_build_stage_task(**_: object) -> BuildStageRunResult:
        return stage_results.pop(0)

    monkeypatch.setattr("course_builder.prefect.flows.load_config_for_step_runner", fake_load_config_for_step_runner)
    monkeypatch.setattr("course_builder.prefect.flows.read_checkpoint", fake_read_checkpoint)
    monkeypatch.setattr("course_builder.prefect.flows.run_build_stage_task", fake_run_build_stage_task)
    monkeypatch.setattr("course_builder.prefect.flows._publish_progress_artifact", lambda **_: None)
    monkeypatch.setattr("course_builder.prefect.flows._publish_section_summary_artifacts", lambda **_: None)
    monkeypatch.setattr("course_builder.prefect.flows.get_run_logger", lambda: logging.getLogger("prefect-test"))

    summary = _run_section_build(BuildRequest(config=tmp_path / "config", build_version=12, section_code="PRE_A1", all_stages=False))

    assert summary["section_code"] == "PRE_A1"
    assert summary["course_version_id"] == "course-version-1"
    assert summary["completed_stage"] == "create_course_build"
    assert summary["ran_stage_count"] == 1
    assert summary["ran_stages"] == ["create_course_build"]


def test_prefect_log_bridge_handler_ignores_prefect_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = PrefectLogBridgeHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    mock_logger = Mock()
    monkeypatch.setattr("course_builder.prefect.flows.get_run_logger", lambda: mock_logger)

    handler.emit(
        logging.LogRecord(
            name="prefect.task_runs",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="prefect internal",
            args=(),
            exc_info=None,
        )
    )

    mock_logger.log.assert_not_called()
