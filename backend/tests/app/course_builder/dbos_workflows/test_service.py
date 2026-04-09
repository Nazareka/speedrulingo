from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
import logging
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.runtime import BuildRequest, CourseBuildOrchestrator, SectionBuildSummary
from course_builder.runtime.run_state import create_stage_run
from course_builder.runtime.runner import BuildProgressSnapshot, BuildStageRunResult
from domain.content.models import CourseBuildLogEvent, CourseBuildRun, CourseBuildStageRun, CourseVersion

COURSE_VERSION_ID = "11111111-1111-1111-1111-111111111111"


def _insert_course_version(db_session: Session) -> None:
    db_session.add(
        CourseVersion(
            id=COURSE_VERSION_ID,
            code="en-ja",
            version=1,
            build_version=12,
            status="draft",
            config_version="v1",
            config_hash="hash",
        )
    )
    db_session.flush()


def _insert_build_run(db_session: Session) -> str:
    build_run = CourseBuildRun(
        workflow_id="workflow-1",
        build_version=12,
        config_path="config/en-ja-v1",
        scope_kind="section",
        section_code="PRE_A1",
        status="running",
        all_stages=True,
        total_stage_count=8,
        course_version_id=COURSE_VERSION_ID,
    )
    db_session.add(build_run)
    db_session.flush()
    return build_run.id


def test_cancel_build_run_marks_parent_child_and_active_stage_runs_cancelled(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setattr(
        "course_builder.runtime.orchestration.SessionLocal",
        lambda: nullcontext(db_session),
    )
    parent_run = CourseBuildRun(
        workflow_id="workflow-parent",
        build_version=12,
        config_path="config/en-ja-v1",
        scope_kind="all_sections",
        status="running",
        all_stages=True,
        total_stage_count=16,
    )
    db_session.add(parent_run)
    db_session.flush()
    child_run = CourseBuildRun(
        parent_build_run_id=parent_run.id,
        build_version=12,
        config_path="config/en-ja-v1",
        scope_kind="section",
        section_code="PRE_A1",
        status="running",
        all_stages=True,
        total_stage_count=8,
    )
    db_session.add(child_run)
    db_session.flush()
    create_stage_run(
        db_session,
        build_run_id=child_run.id,
        section_code="PRE_A1",
        stage_name="bootstrap_catalog",
        stage_index=1,
    )
    db_session.commit()

    CourseBuildOrchestrator.cancel_build_run(build_run_id=parent_run.id)

    db_session.expire_all()
    refreshed_parent = db_session.get(CourseBuildRun, parent_run.id)
    refreshed_child = db_session.get(CourseBuildRun, child_run.id)
    stage_runs = db_session.scalars(select(CourseBuildStageRun)).all()

    assert refreshed_parent is not None
    assert refreshed_child is not None
    assert refreshed_parent.status == "cancelled"
    assert refreshed_child.status == "cancelled"
    assert len(stage_runs) == 1
    assert stage_runs[0].status == "cancelled"


def test_run_section_until_done_does_not_start_next_stage_after_cancel(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    tmp_path: Path,
) -> None:
    orchestrator = CourseBuildOrchestrator()
    _insert_course_version(db_session)
    monkeypatch.setattr(
        "course_builder.runtime.orchestration.SessionLocal",
        lambda: nullcontext(db_session),
    )

    progress_snapshots = [
        BuildProgressSnapshot(
            build_run_id="build-run-1",
            build_version=12,
            section_code="PRE_A1",
            course_version_id=None,
            next_stage_index=0,
        ),
        BuildProgressSnapshot(
            build_run_id="build-run-1",
            build_version=12,
            section_code="PRE_A1",
            course_version_id=COURSE_VERSION_ID,
            next_stage_index=1,
        ),
    ]
    monkeypatch.setattr(
        orchestrator,
        "read_build_progress",
        lambda **_: progress_snapshots.pop(0),
    )

    cancel_checks = iter([False, True])
    monkeypatch.setattr(
        orchestrator,
        "_is_run_cancelled",
        lambda **_: next(cancel_checks),
    )

    stage_calls: list[str] = []

    def fake_stage_runner(**_: object) -> BuildStageRunResult:
        stage_calls.append("create_course_build")
        return BuildStageRunResult(
            build_version=12,
            course_version_id=COURSE_VERSION_ID,
            completed_stage_name="create_course_build",
            completed_stage_index=0,
            remaining_stage_count=7,
        )

    summary = orchestrator.run_section_until_done(
        BuildRequest(config=tmp_path / "config", build_version=12, section_code="PRE_A1", all_stages=True),
        logger=logging.getLogger("test-course-builder"),
        stage_runner=fake_stage_runner,
    )

    assert stage_calls == ["create_course_build"]
    assert summary["ran_stages"] == ["create_course_build"]


def test_run_section_until_done_returns_plain_summary(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    tmp_path: Path,
) -> None:
    orchestrator = CourseBuildOrchestrator()
    _insert_course_version(db_session)
    progress_snapshots = [
        BuildProgressSnapshot(
            build_run_id="build-run-1",
            build_version=12,
            section_code="PRE_A1",
            course_version_id=None,
            next_stage_index=0,
        ),
        BuildProgressSnapshot(
            build_run_id="build-run-1",
            build_version=12,
            section_code="PRE_A1",
            course_version_id=COURSE_VERSION_ID,
            next_stage_index=1,
        ),
    ]
    progress_updates: list[int] = []

    monkeypatch.setattr(
        orchestrator,
        "read_build_progress",
        lambda **_: progress_snapshots.pop(0),
    )
    monkeypatch.setattr(
        "course_builder.runtime.orchestration.SessionLocal",
        lambda: nullcontext(db_session),
    )

    def fake_stage_runner(**_: object) -> BuildStageRunResult:
        return BuildStageRunResult(
            build_version=12,
            course_version_id=COURSE_VERSION_ID,
            completed_stage_name="create_course_build",
            completed_stage_index=0,
            remaining_stage_count=7,
        )

    summary = orchestrator.run_section_until_done(
        BuildRequest(config=tmp_path / "config", build_version=12, section_code="PRE_A1", all_stages=False),
        logger=logging.getLogger("test-course-builder"),
        stage_runner=fake_stage_runner,
        progress_reporter=lambda progress: progress_updates.append(progress.completed_stage_count),
    )

    assert summary["section_code"] == "PRE_A1"
    assert summary["course_version_id"] == COURSE_VERSION_ID
    assert summary["completed_stage"] == "create_course_build"
    assert summary["ran_stage_count"] == 1
    assert summary["ran_stages"] == ["create_course_build"]
    assert summary["was_noop"] is False
    assert progress_updates == [0, 1]


def test_run_all_sections_until_done_skips_completed_sections(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    tmp_path: Path,
) -> None:
    orchestrator = CourseBuildOrchestrator()
    _insert_course_version(db_session)

    monkeypatch.setattr(
        "course_builder.runtime.orchestration.read_declared_section_codes",
        lambda _: ["PRE_A1", "A1_1"],
    )
    monkeypatch.setattr(
        orchestrator,
        "is_section_completed",
        lambda *, build_version, config_path, section_code: section_code == "PRE_A1",
    )
    monkeypatch.setattr(
        "course_builder.runtime.orchestration.SessionLocal",
        lambda: nullcontext(db_session),
    )

    def fake_section_runner(
        request: BuildRequest,
        *,
        build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
    ) -> SectionBuildSummary:
        _ = build_run_id
        _ = parent_build_run_id
        return {
            "build_run_id": "build-run-1",
            "build_version": 12,
            "section_code": request.section_code or "",
            "course_version_id": COURSE_VERSION_ID,
            "completed_stage": "bootstrap_catalog",
            "completed_stage_index": 1,
            "remaining_stage_count": 6,
            "ran_stage_count": 1,
            "ran_stages": ["bootstrap_catalog"],
            "was_noop": False,
        }

    summary = orchestrator.run_all_sections_until_done(
        BuildRequest(config=tmp_path / "config", build_version=12, all_sections=True),
        logger=logging.getLogger("test-course-builder"),
        section_runner=fake_section_runner,
    )

    assert summary["build_version"] == 12
    assert summary["build_run_id"]
    assert summary["ran_section_count"] == 1
    assert [item["section_code"] for item in summary["ran_sections"]] == ["A1_1"]
    assert summary["last_section"] is not None
    assert summary["last_section"]["section_code"] == "A1_1"
    assert summary["was_noop"] is False


def test_run_section_until_done_persists_build_run_state(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    tmp_path: Path,
) -> None:
    orchestrator = CourseBuildOrchestrator()
    _insert_course_version(db_session)
    progress_snapshots = [
        BuildProgressSnapshot(
            build_run_id="build-run-1",
            build_version=12,
            section_code="PRE_A1",
            course_version_id=None,
            next_stage_index=0,
        ),
        BuildProgressSnapshot(
            build_run_id="build-run-1",
            build_version=12,
            section_code="PRE_A1",
            course_version_id=COURSE_VERSION_ID,
            next_stage_index=1,
        ),
    ]

    monkeypatch.setattr(
        "course_builder.runtime.orchestration.SessionLocal",
        lambda: nullcontext(db_session),
    )
    monkeypatch.setattr(
        orchestrator,
        "read_build_progress",
        lambda **_: progress_snapshots.pop(0),
    )

    def fake_stage_runner(**_: object) -> BuildStageRunResult:
        return BuildStageRunResult(
            build_version=12,
            course_version_id=COURSE_VERSION_ID,
            completed_stage_name="create_course_build",
            completed_stage_index=0,
            remaining_stage_count=7,
        )

    summary = orchestrator.run_section_until_done(
        BuildRequest(config=tmp_path / "config", build_version=12, section_code="PRE_A1", all_stages=False),
        logger=logging.getLogger("test-course-builder"),
        stage_runner=fake_stage_runner,
    )

    build_runs = db_session.scalars(select(CourseBuildRun)).all()
    stage_runs = db_session.scalars(select(CourseBuildStageRun)).all()
    log_events = db_session.scalars(select(CourseBuildLogEvent)).all()

    assert summary["build_run_id"] == build_runs[0].id
    assert len(build_runs) == 1
    assert build_runs[0].scope_kind == "section"
    assert build_runs[0].status == "completed"
    assert build_runs[0].section_code == "PRE_A1"
    assert build_runs[0].course_version_id == COURSE_VERSION_ID
    assert build_runs[0].completed_stage_count == 1
    assert build_runs[0].total_stage_count == 8
    assert build_runs[0].current_stage_name is None

    assert len(stage_runs) == 1
    assert stage_runs[0].section_code == "PRE_A1"
    assert stage_runs[0].stage_name == "create_course_build"
    assert stage_runs[0].stage_index == 0
    assert stage_runs[0].status == "completed"

    assert [event.level for event in log_events] == ["INFO", "INFO", "INFO"]
    assert any("Starting section build" in event.message for event in log_events)
    assert any("Running stage create_course_build" in event.message for event in log_events)
    assert any("Completed stage create_course_build" in event.message for event in log_events)


def test_run_section_until_done_returns_noop_summary_when_already_complete(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    tmp_path: Path,
) -> None:
    orchestrator = CourseBuildOrchestrator()
    _insert_course_version(db_session)
    monkeypatch.setattr(
        "course_builder.runtime.orchestration.SessionLocal",
        lambda: nullcontext(db_session),
    )
    monkeypatch.setattr(
        orchestrator,
        "read_build_progress",
        lambda **_: BuildProgressSnapshot(
            build_run_id="build-run-1",
            build_version=12,
            section_code="PRE_A1",
            course_version_id=COURSE_VERSION_ID,
            next_stage_index=8,
            last_attempted_stage_name="release",
        ),
    )

    summary = orchestrator.run_section_until_done(
        BuildRequest(config=tmp_path / "config", build_version=12, section_code="PRE_A1", all_stages=True),
        logger=logging.getLogger("test-course-builder"),
    )

    assert summary["was_noop"] is True
    assert summary["ran_stage_count"] == 0
    assert summary["completed_stage"] == "release"
    assert summary["completed_stage_index"] == 7
    assert summary["remaining_stage_count"] == 0


def test_run_one_stage_persists_stage_internal_logs(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    tmp_path: Path,
) -> None:
    orchestrator = CourseBuildOrchestrator()
    _insert_course_version(db_session)
    build_run_id = _insert_build_run(db_session)

    monkeypatch.setattr(
        "course_builder.runtime.orchestration.SessionLocal",
        lambda: nullcontext(db_session),
    )
    monkeypatch.setattr(
        "course_builder.runtime.orchestration.load_config_for_step_runner",
        lambda config_path, *, section_code: object(),
    )
    monkeypatch.setattr(
        "course_builder.runtime.orchestration.build_langsmith_tracing_context",
        lambda *, build_version, section_code: nullcontext(),
    )

    def fake_run_build_stage_with_attempt_log(
        *,
        db: Session,
        config: object,
        build_version: int,
        build_run_id: str | None = None,
        extra_root_handler: logging.Handler | None = None,
    ) -> BuildStageRunResult:
        _ = db
        _ = config
        _ = build_version
        _ = build_run_id
        assert extra_root_handler is not None
        logging.getLogger("course_builder.fake").info("internal stage log line")
        return BuildStageRunResult(
            build_version=12,
            course_version_id=COURSE_VERSION_ID,
            completed_stage_name="bootstrap_catalog",
            completed_stage_index=1,
            remaining_stage_count=6,
        )

    monkeypatch.setattr(
        "course_builder.runtime.orchestration.run_build_stage_with_attempt_log",
        fake_run_build_stage_with_attempt_log,
    )

    result = orchestrator.run_one_stage(
        config_path=tmp_path / "config",
        section_code="PRE_A1",
        build_version=12,
        build_run_id=build_run_id,
        stage_name="bootstrap_catalog",
    )

    assert result.completed_stage_name == "bootstrap_catalog"
    log_events = db_session.scalars(select(CourseBuildLogEvent)).all()
    assert [event.message for event in log_events] == ["internal stage log line"]
    build_run = db_session.get(CourseBuildRun, build_run_id)
    assert build_run is not None
    assert build_run.current_stage_name == "bootstrap_catalog"
    assert build_run.last_heartbeat_at is not None


def test_create_stage_run_reuses_existing_scope_row(db_session: Session) -> None:
    _insert_course_version(db_session)
    build_run_id = _insert_build_run(db_session)

    first = create_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="create_course_build",
        stage_index=0,
    )
    db_session.flush()
    first.status = "failed"
    first.error_message = "boom"
    first.started_at = datetime(2020, 1, 1, tzinfo=UTC)
    db_session.flush()

    second = create_stage_run(
        db_session,
        build_run_id=build_run_id,
        section_code="PRE_A1",
        stage_name="create_course_build",
        stage_index=0,
    )
    db_session.flush()

    stage_runs = db_session.scalars(select(CourseBuildStageRun)).all()

    assert second.id == first.id
    assert len(stage_runs) == 1
    assert second.status == "running"
    assert second.error_message is None
    assert second.started_at > datetime(2020, 1, 1, tzinfo=UTC)
