from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from course_builder.build_runs.models import BuildRequest
from course_builder.build_runs.queries import get_build_run, get_stage_run_by_scope
from domain.content.models import CourseBuildLogEvent, CourseBuildRun, CourseBuildStageRun

RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_CANCELLED = "cancelled"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
STAGE_STATUS_CANCELLED = "cancelled"
STAGE_STATUS_COMPLETED = "completed"
STAGE_STATUS_FAILED = "failed"
STAGE_STATUS_RUNNING = "running"


def utc_now() -> datetime:
    return datetime.now(UTC)


def create_build_run(
    db: Session,
    *,
    request: BuildRequest,
    scope_kind: str,
    total_stage_count: int,
    parent_build_run_id: str | None = None,
    workflow_id: str | None = None,
    requested_by: str | None = None,
) -> CourseBuildRun:
    build_run = CourseBuildRun(
        parent_build_run_id=parent_build_run_id,
        workflow_id=workflow_id,
        build_version=request.build_version,
        config_path=str(request.config),
        scope_kind=scope_kind,
        section_code=request.section_code,
        status=RUN_STATUS_QUEUED,
        requested_by=requested_by,
        all_stages=request.all_stages,
        completed_stage_count=0,
        total_stage_count=total_stage_count,
    )
    db.add(build_run)
    db.flush()
    return build_run


def mark_build_run_running(
    build_run: CourseBuildRun,
    *,
    completed_stage_count: int,
    current_stage_name: str | None,
) -> None:
    now = utc_now()
    build_run.status = RUN_STATUS_RUNNING
    if build_run.started_at is None:
        build_run.started_at = now
    build_run.completed_stage_count = completed_stage_count
    build_run.current_stage_name = current_stage_name
    build_run.last_heartbeat_at = now


def mark_build_run_completed(
    build_run: CourseBuildRun,
    *,
    course_version_id: str | None,
    completed_stage_count: int,
) -> None:
    now = utc_now()
    build_run.status = RUN_STATUS_COMPLETED
    build_run.course_version_id = course_version_id
    build_run.completed_stage_count = completed_stage_count
    build_run.current_stage_name = None
    build_run.last_heartbeat_at = now
    build_run.finished_at = now
    build_run.error_message = None


def mark_build_run_failed(
    build_run: CourseBuildRun,
    *,
    error_message: str,
    current_stage_name: str | None,
) -> None:
    now = utc_now()
    build_run.status = RUN_STATUS_FAILED
    build_run.current_stage_name = current_stage_name
    build_run.last_heartbeat_at = now
    build_run.finished_at = now
    build_run.error_message = error_message


def mark_build_run_cancelled(build_run: CourseBuildRun) -> None:
    now = utc_now()
    build_run.status = RUN_STATUS_CANCELLED
    build_run.current_stage_name = None
    build_run.last_heartbeat_at = now
    build_run.finished_at = now
    build_run.error_message = None


def create_stage_run(
    db: Session,
    *,
    build_run_id: str,
    section_code: str,
    stage_name: str,
    stage_index: int,
) -> CourseBuildStageRun:
    existing_stage_run = get_stage_run_by_scope(
        db,
        build_run_id=build_run_id,
        section_code=section_code,
        stage_index=stage_index,
    )
    if existing_stage_run is not None:
        existing_stage_run.started_at = utc_now()
        existing_stage_run.stage_name = stage_name
        existing_stage_run.status = STAGE_STATUS_RUNNING
        existing_stage_run.finished_at = None
        existing_stage_run.error_message = None
        db.flush()
        return existing_stage_run
    stage_run = CourseBuildStageRun(
        build_run_id=build_run_id,
        section_code=section_code,
        stage_name=stage_name,
        stage_index=stage_index,
        status=STAGE_STATUS_RUNNING,
    )
    db.add(stage_run)
    db.flush()
    return stage_run


def mark_stage_run_completed(stage_run: CourseBuildStageRun) -> None:
    stage_run.status = STAGE_STATUS_COMPLETED
    stage_run.finished_at = utc_now()
    stage_run.error_message = None


def mark_stage_run_failed(stage_run: CourseBuildStageRun, *, error_message: str) -> None:
    stage_run.status = STAGE_STATUS_FAILED
    stage_run.finished_at = utc_now()
    stage_run.error_message = error_message


def mark_stage_run_cancelled(stage_run: CourseBuildStageRun) -> None:
    stage_run.status = STAGE_STATUS_CANCELLED
    stage_run.finished_at = utc_now()
    stage_run.error_message = None


def append_build_log_event(
    db: Session,
    *,
    build_run_id: str,
    level: str,
    message: str,
    section_code: str | None = None,
    stage_name: str | None = None,
) -> None:
    db.add(
        CourseBuildLogEvent(
            build_run_id=build_run_id,
            section_code=section_code,
            stage_name=stage_name,
            level=level,
            message=message,
        )
    )
    db.flush()


def touch_build_run_heartbeat(
    db: Session,
    *,
    build_run_id: str,
    current_stage_name: str | None = None,
) -> None:
    build_run = get_build_run(db, build_run_id=build_run_id)
    if build_run is None:
        msg = f"Unknown build_run_id={build_run_id}"
        raise ValueError(msg)
    build_run.last_heartbeat_at = utc_now()
    if current_stage_name is not None:
        build_run.current_stage_name = current_stage_name
    db.flush()
