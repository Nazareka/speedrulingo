from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from domain.content.models import CourseBuildLogEvent, CourseBuildRun, CourseBuildStageRun, CourseVersion


def list_build_runs(
    db: Session,
    *,
    limit: int = 50,
) -> list[CourseBuildRun]:
    return list(
        db.scalars(
            select(CourseBuildRun)
            .where(CourseBuildRun.parent_build_run_id.is_(None))
            .order_by(
                CourseBuildRun.created_at.desc(),
                CourseBuildRun.build_version.desc(),
                CourseBuildRun.id.desc(),
            )
            .limit(limit)
        )
    )


def get_build_run(db: Session, *, build_run_id: str) -> CourseBuildRun | None:
    return db.get(CourseBuildRun, build_run_id)


def get_build_run_by_workflow_id(db: Session, *, workflow_id: str) -> CourseBuildRun | None:
    return db.scalar(
        select(CourseBuildRun)
        .where(
            CourseBuildRun.workflow_id == workflow_id,
            CourseBuildRun.parent_build_run_id.is_(None),
        )
        .order_by(desc(CourseBuildRun.created_at), desc(CourseBuildRun.id))
        .limit(1)
    )


def get_stage_run(db: Session, *, stage_run_id: str) -> CourseBuildStageRun | None:
    return db.get(CourseBuildStageRun, stage_run_id)


def get_stage_run_by_scope(
    db: Session,
    *,
    build_run_id: str,
    section_code: str,
    stage_index: int,
) -> CourseBuildStageRun | None:
    return db.scalar(
        select(CourseBuildStageRun).where(
            CourseBuildStageRun.build_run_id == build_run_id,
            CourseBuildStageRun.section_code == section_code,
            CourseBuildStageRun.stage_index == stage_index,
        )
    )


def get_course_version(db: Session, *, course_version_id: str) -> CourseVersion | None:
    return db.get(CourseVersion, course_version_id)


def get_completed_stage_indexes(
    db: Session,
    *,
    build_run_id: str,
    section_code: str | None,
) -> set[int]:
    filters = [
        CourseBuildStageRun.build_run_id == build_run_id,
        CourseBuildStageRun.status == "completed",
    ]
    if section_code is not None:
        filters.append(CourseBuildStageRun.section_code == section_code)
    return set(
        db.scalars(
            select(CourseBuildStageRun.stage_index)
            .where(*filters)
            .distinct()
        )
    )


def list_completed_stage_identities(
    db: Session,
    *,
    build_run_id: str,
    section_code: str | None,
) -> list[tuple[int, str]]:
    filters = [
        CourseBuildStageRun.build_run_id == build_run_id,
        CourseBuildStageRun.status == "completed",
    ]
    if section_code is not None:
        filters.append(CourseBuildStageRun.section_code == section_code)
    return list(
        db.execute(
            select(CourseBuildStageRun.stage_index, CourseBuildStageRun.stage_name)
            .where(*filters)
            .order_by(CourseBuildStageRun.stage_index)
            .distinct()
        )
        .tuples()
        .all()
    )


def get_latest_attempted_stage_name(
    db: Session,
    *,
    build_run_id: str,
    section_code: str | None,
) -> str | None:
    filters = [CourseBuildStageRun.build_run_id == build_run_id]
    if section_code is not None:
        filters.append(CourseBuildStageRun.section_code == section_code)
    return db.scalar(
        select(CourseBuildStageRun.stage_name)
        .where(*filters)
        .order_by(desc(CourseBuildStageRun.started_at), desc(CourseBuildStageRun.stage_index))
        .limit(1)
    )


def get_latest_course_version_id_for_build_run(
    db: Session,
    *,
    build_run: CourseBuildRun,
) -> str | None:
    if build_run.course_version_id is not None:
        return build_run.course_version_id
    return db.scalar(
        select(CourseVersion.id)
        .where(CourseVersion.build_version == build_run.build_version)
        .order_by(desc(CourseVersion.created_at))
        .limit(1)
    )


def get_latest_section_build_run_id(
    db: Session,
    *,
    build_version: int,
    config_path: str,
    section_code: str,
) -> str | None:
    return db.scalar(
        select(CourseBuildRun.id)
        .where(
            CourseBuildRun.build_version == build_version,
            CourseBuildRun.config_path == config_path,
            CourseBuildRun.scope_kind == "section",
            CourseBuildRun.section_code == section_code,
        )
        .order_by(desc(CourseBuildRun.created_at))
        .limit(1)
    )


def get_existing_course_version_for_build(
    db: Session,
    *,
    course_code: str,
    course_version: int,
    build_version: int,
) -> CourseVersion | None:
    return db.scalar(
        select(CourseVersion).where(
            CourseVersion.code == course_code,
            CourseVersion.version == course_version,
            CourseVersion.build_version == build_version,
        )
    )


def get_latest_completed_section_build_run(
    db: Session,
    *,
    build_version: int,
    config_path: str,
    section_code: str,
) -> CourseBuildRun | None:
    return db.scalar(
        select(CourseBuildRun)
        .where(
            CourseBuildRun.build_version == build_version,
            CourseBuildRun.config_path == config_path,
            CourseBuildRun.scope_kind == "section",
            CourseBuildRun.section_code == section_code,
            CourseBuildRun.status == "completed",
        )
        .order_by(desc(CourseBuildRun.created_at), desc(CourseBuildRun.id))
        .limit(1)
    )


def list_child_section_build_runs(
    db: Session,
    *,
    parent_build_run_id: str,
) -> list[CourseBuildRun]:
    return list(
        db.scalars(
            select(CourseBuildRun)
            .where(
                CourseBuildRun.parent_build_run_id == parent_build_run_id,
                CourseBuildRun.scope_kind == "section",
            )
            .order_by(CourseBuildRun.created_at, CourseBuildRun.id)
        )
    )


def list_descendant_build_runs(
    db: Session,
    *,
    parent_build_run_id: str,
) -> list[CourseBuildRun]:
    return list(
        db.scalars(
            select(CourseBuildRun)
            .where(CourseBuildRun.parent_build_run_id == parent_build_run_id)
            .order_by(CourseBuildRun.created_at, CourseBuildRun.id)
        )
    )


def list_stage_runs(
    db: Session,
    *,
    build_run_id: str,
) -> list[CourseBuildStageRun]:
    return list(
        db.scalars(
            select(CourseBuildStageRun)
            .where(CourseBuildStageRun.build_run_id == build_run_id)
            .order_by(CourseBuildStageRun.stage_index, CourseBuildStageRun.started_at)
        )
    )


def list_active_stage_runs(
    db: Session,
    *,
    build_run_id: str,
) -> list[CourseBuildStageRun]:
    return list(
        db.scalars(
            select(CourseBuildStageRun)
            .where(
                CourseBuildStageRun.build_run_id == build_run_id,
                CourseBuildStageRun.status == "running",
            )
            .order_by(CourseBuildStageRun.stage_index, CourseBuildStageRun.started_at)
        )
    )


def list_log_events(
    db: Session,
    *,
    build_run_id: str,
    limit: int = 500,
) -> list[CourseBuildLogEvent]:
    return list(
        db.scalars(
            select(CourseBuildLogEvent)
            .where(CourseBuildLogEvent.build_run_id == build_run_id)
            .order_by(CourseBuildLogEvent.sequence_number)
            .limit(limit)
        )
    )


def list_log_events_for_build_run_ids(
    db: Session,
    *,
    build_run_ids: list[str],
    limit: int = 500,
) -> list[CourseBuildLogEvent]:
    if not build_run_ids:
        return []
    return list(
        db.scalars(
            select(CourseBuildLogEvent)
            .where(CourseBuildLogEvent.build_run_id.in_(build_run_ids))
            # sequence_number is a global unique sequence, so this preserves
            # true append order even when aggregating parent and child runs.
            .order_by(CourseBuildLogEvent.sequence_number)
            .limit(limit)
        )
    )
