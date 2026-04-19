"""Build-run progress, logging, and cancellation — shared by orchestration and DBOS workflows."""

from __future__ import annotations

from course_builder.build_runs.live_updates import publish_build_run_event
from course_builder.build_runs.models import BuildRequest
from course_builder.build_runs.queries import (
    get_build_run,
    get_stage_run,
    list_active_stage_runs,
    list_completed_stage_identities,
    list_descendant_build_runs,
)
from course_builder.build_runs.run_state import (
    RUN_STATUS_CANCELLED,
    append_build_log_event,
    create_build_run,
    create_stage_run,
    mark_build_run_cancelled,
    mark_build_run_completed,
    mark_build_run_failed,
    mark_build_run_running,
    mark_stage_run_cancelled,
    mark_stage_run_completed,
    mark_stage_run_failed,
)
from db.engine import SessionLocal
from domain.content.models import CourseBuildRun


class BuildRunTracking:
    """Session-scoped DB updates + Redis notifications for a course build run."""

    @staticmethod
    def create_run_row(
        *,
        request: BuildRequest,
        scope_kind: str,
        total_stage_count: int,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
        requested_by: str | None = None,
    ) -> CourseBuildRun:
        with SessionLocal() as db:
            build_run = create_build_run(
                db,
                request=request,
                scope_kind=scope_kind,
                total_stage_count=total_stage_count,
                parent_build_run_id=parent_build_run_id,
                workflow_id=workflow_id,
                requested_by=requested_by,
            )
            db.commit()
            publish_build_run_event(
                event_type="build_run.created",
                build_run_id=build_run.id,
                parent_build_run_id=build_run.parent_build_run_id,
            )
            db.refresh(build_run)
            return build_run

    @staticmethod
    def log_message(
        *,
        build_run_id: str,
        level: str,
        message: str,
        section_code: str | None = None,
        stage_name: str | None = None,
    ) -> None:
        with SessionLocal() as db:
            append_build_log_event(
                db,
                build_run_id=build_run_id,
                level=level,
                message=message,
                section_code=section_code,
                stage_name=stage_name,
            )
            db.commit()
            build_run = get_build_run(db, build_run_id=build_run_id)
            publish_build_run_event(
                event_type="build_run.log_appended",
                build_run_id=build_run_id,
                parent_build_run_id=build_run.parent_build_run_id if build_run is not None else None,
            )

    @staticmethod
    def sync_progress(
        *,
        build_run_id: str,
        completed_stage_count: int,
        current_stage_name: str | None,
        course_version_id: str | None = None,
    ) -> None:
        with SessionLocal() as db:
            build_run = get_build_run(db, build_run_id=build_run_id)
            if build_run is None:
                msg = f"Unknown build_run_id={build_run_id}"
                raise ValueError(msg)
            if build_run.status == RUN_STATUS_CANCELLED:
                return
            mark_build_run_running(
                build_run,
                completed_stage_count=completed_stage_count,
                current_stage_name=current_stage_name,
            )
            if course_version_id is not None:
                build_run.course_version_id = course_version_id
            db.commit()
            publish_build_run_event(
                event_type="build_run.progress_updated",
                build_run_id=build_run_id,
                parent_build_run_id=build_run.parent_build_run_id,
            )

    @staticmethod
    def seed_completed_stages_from_run(
        *,
        source_build_run_id: str,
        target_build_run_id: str,
        section_code: str,
    ) -> None:
        with SessionLocal() as db:
            source_build_run = get_build_run(db, build_run_id=source_build_run_id)
            if source_build_run is None:
                msg = f"Unknown source_build_run_id={source_build_run_id}"
                raise ValueError(msg)
            target_build_run = get_build_run(db, build_run_id=target_build_run_id)
            if target_build_run is None:
                msg = f"Unknown target_build_run_id={target_build_run_id}"
                raise ValueError(msg)
            completed_stage_rows = list_completed_stage_identities(
                db,
                build_run_id=source_build_run_id,
                section_code=section_code,
            )
            for stage_index, stage_name in completed_stage_rows:
                stage_run = create_stage_run(
                    db,
                    build_run_id=target_build_run_id,
                    section_code=section_code,
                    stage_name=stage_name,
                    stage_index=stage_index,
                )
                mark_stage_run_completed(stage_run)
            if source_build_run.course_version_id is not None:
                target_build_run.course_version_id = source_build_run.course_version_id
            db.commit()
            publish_build_run_event(
                event_type="build_run.progress_updated",
                build_run_id=target_build_run_id,
                parent_build_run_id=target_build_run.parent_build_run_id,
            )

    @staticmethod
    def mark_completed(
        *,
        build_run_id: str,
        course_version_id: str | None,
        completed_stage_count: int,
    ) -> None:
        with SessionLocal() as db:
            build_run = get_build_run(db, build_run_id=build_run_id)
            if build_run is None:
                msg = f"Unknown build_run_id={build_run_id}"
                raise ValueError(msg)
            if build_run.status == RUN_STATUS_CANCELLED:
                return
            mark_build_run_completed(
                build_run,
                course_version_id=course_version_id,
                completed_stage_count=completed_stage_count,
            )
            db.commit()
            publish_build_run_event(
                event_type="build_run.completed",
                build_run_id=build_run_id,
                parent_build_run_id=build_run.parent_build_run_id,
            )

    @staticmethod
    def mark_failed(
        *,
        build_run_id: str,
        error_message: str,
        current_stage_name: str | None,
    ) -> None:
        with SessionLocal() as db:
            build_run = get_build_run(db, build_run_id=build_run_id)
            if build_run is None:
                msg = f"Unknown build_run_id={build_run_id}"
                raise ValueError(msg)
            if build_run.status == RUN_STATUS_CANCELLED:
                return
            mark_build_run_failed(
                build_run,
                error_message=error_message,
                current_stage_name=current_stage_name,
            )
            db.commit()
            publish_build_run_event(
                event_type="build_run.failed",
                build_run_id=build_run_id,
                parent_build_run_id=build_run.parent_build_run_id,
            )

    @staticmethod
    def mark_cancelled_record(*, build_run_id: str) -> None:
        with SessionLocal() as db:
            build_run = get_build_run(db, build_run_id=build_run_id)
            if build_run is None:
                msg = f"Unknown build_run_id={build_run_id}"
                raise ValueError(msg)
            mark_build_run_cancelled(build_run)
            db.commit()
            publish_build_run_event(
                event_type="build_run.cancelled",
                build_run_id=build_run_id,
                parent_build_run_id=build_run.parent_build_run_id,
            )

    @staticmethod
    def create_stage_run_row(
        *,
        build_run_id: str,
        section_code: str,
        stage_name: str,
        stage_index: int,
    ) -> str:
        with SessionLocal() as db:
            stage_run = create_stage_run(
                db,
                build_run_id=build_run_id,
                section_code=section_code,
                stage_name=stage_name,
                stage_index=stage_index,
            )
            db.commit()
            build_run = get_build_run(db, build_run_id=build_run_id)
            publish_build_run_event(
                event_type="build_run.stage_started",
                build_run_id=build_run_id,
                parent_build_run_id=build_run.parent_build_run_id if build_run is not None else None,
            )
            return stage_run.id

    @staticmethod
    def mark_stage_completed(*, stage_run_id: str) -> None:
        with SessionLocal() as db:
            stage_run = get_stage_run(db, stage_run_id=stage_run_id)
            if stage_run is None:
                msg = f"Unknown stage_run_id={stage_run_id}"
                raise ValueError(msg)
            mark_stage_run_completed(stage_run)
            db.commit()
            build_run = get_build_run(db, build_run_id=stage_run.build_run_id)
            publish_build_run_event(
                event_type="build_run.stage_completed",
                build_run_id=stage_run.build_run_id,
                parent_build_run_id=build_run.parent_build_run_id if build_run is not None else None,
            )

    @staticmethod
    def mark_stage_failed(*, stage_run_id: str, error_message: str) -> None:
        with SessionLocal() as db:
            stage_run = get_stage_run(db, stage_run_id=stage_run_id)
            if stage_run is None:
                msg = f"Unknown stage_run_id={stage_run_id}"
                raise ValueError(msg)
            mark_stage_run_failed(stage_run, error_message=error_message)
            db.commit()
            build_run = get_build_run(db, build_run_id=stage_run.build_run_id)
            publish_build_run_event(
                event_type="build_run.stage_failed",
                build_run_id=stage_run.build_run_id,
                parent_build_run_id=build_run.parent_build_run_id if build_run is not None else None,
            )

    @staticmethod
    def is_cancelled(*, build_run_id: str) -> bool:
        with SessionLocal() as db:
            build_run = get_build_run(db, build_run_id=build_run_id)
            if build_run is None:
                msg = f"Unknown build_run_id={build_run_id}"
                raise ValueError(msg)
            return build_run.status == RUN_STATUS_CANCELLED

    @staticmethod
    def cancel_build_run(*, build_run_id: str) -> None:
        with SessionLocal() as db:
            build_run = get_build_run(db, build_run_id=build_run_id)
            if build_run is None:
                msg = f"Unknown build_run_id={build_run_id}"
                raise ValueError(msg)
            affected_runs = [build_run, *list_descendant_build_runs(db, parent_build_run_id=build_run.id)]
            for affected_run in affected_runs:
                if affected_run.status in {"queued", "running"}:
                    mark_build_run_cancelled(affected_run)
                for stage_run in list_active_stage_runs(db, build_run_id=affected_run.id):
                    mark_stage_run_cancelled(stage_run)
            db.commit()
            for affected_run in affected_runs:
                publish_build_run_event(
                    event_type="build_run.cancelled",
                    build_run_id=affected_run.id,
                    parent_build_run_id=affected_run.parent_build_run_id,
                )
