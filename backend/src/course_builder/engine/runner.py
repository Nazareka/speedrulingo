from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, cast

from sqlalchemy.exc import IntegrityError, ResourceClosedError
from sqlalchemy.orm import Session

from course_builder.build_runs.queries import (
    get_build_run,
    get_completed_stage_indexes,
    get_course_version,
    get_existing_course_version_for_build,
    get_latest_attempted_stage_name,
    get_latest_course_version_id_for_build_run,
    get_latest_section_build_run_id,
    list_completed_stage_identities,
)
from course_builder.config import CourseBuildConfig, CourseBuildConfigLoader
from course_builder.engine.models import BuildContext, BuildStep, compute_config_hash
from course_builder.engine.persistence import create_draft_build_row
from course_builder.engine.stage_registry import get_registered_build_stages
from domain.content.models import CourseBuildRun

LOGGER = logging.getLogger(__name__)
STAGE0_CREATE_COURSE_BUILD = "create_course_build"


@dataclass(frozen=True, slots=True)
class BuildProgressSnapshot:
    build_run_id: str
    build_version: int
    section_code: str | None
    course_version_id: str | None
    next_stage_index: int
    last_attempted_stage_name: str | None = None

    @property
    def completed_stage_count(self) -> int:
        return self.next_stage_index


@dataclass(frozen=True, slots=True)
class BuildStageRunResult:
    build_version: int
    course_version_id: str
    completed_stage_name: str
    completed_stage_index: int
    remaining_stage_count: int


class _CommitDeferredSession:
    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        self._session.flush()

    def rollback(self) -> None:
        self._session.rollback()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)


def get_build_stages() -> tuple[BuildStep, ...]:
    return get_registered_build_stages()


def load_config_for_step_runner(config_path: Path, *, section_code: str) -> CourseBuildConfig:
    return CourseBuildConfigLoader.load_and_validate(config_path, section_code=section_code)


def _total_stage_count(stages: tuple[BuildStep, ...]) -> int:
    return len(stages) + 1


def _resolve_section_code(*, build_run: CourseBuildRun, section_code: str | None) -> str | None:
    return section_code or build_run.section_code


def _expected_stage_name_by_index(*, stages: tuple[BuildStep, ...], stage_index: int) -> str:
    if stage_index == 0:
        return STAGE0_CREATE_COURSE_BUILD
    total_stage_count = _total_stage_count(stages)
    if stage_index < 0 or stage_index >= total_stage_count:
        msg = f"Recorded stage_index {stage_index} is outside the valid range 0..{total_stage_count - 1}"
        raise ValueError(msg)
    return stages[stage_index - 1].name


def _validate_stage_history_matches_registry(
    db: Session,
    *,
    build_run_id: str,
    section_code: str | None,
    stages: tuple[BuildStep, ...],
) -> None:
    rows = list_completed_stage_identities(
        db,
        build_run_id=build_run_id,
        section_code=section_code,
    )
    for stage_index, stage_name in rows:
        expected_stage_name = _expected_stage_name_by_index(stages=stages, stage_index=stage_index)
        if stage_name != expected_stage_name:
            msg = (
                "Build stage registry changed and existing stage progress can no longer be resumed safely: "
                f"build_run_id={build_run_id} stage_index={stage_index} "
                f"recorded_stage_name={stage_name!r} expected_stage_name={expected_stage_name!r}"
            )
            raise ValueError(msg)


def _derived_next_stage_index(
    *,
    stages: tuple[BuildStep, ...],
    completed_stage_indexes: set[int],
) -> int:
    next_stage_index = 0
    total_stage_count = _total_stage_count(stages)
    while next_stage_index in completed_stage_indexes:
        next_stage_index += 1
    if next_stage_index > total_stage_count:
        msg = f"Derived next_stage_index must be <= {total_stage_count}, got {next_stage_index}"
        raise ValueError(msg)
    return next_stage_index


def read_build_progress(
    db: Session,
    *,
    build_run_id: str,
    section_code: str | None = None,
) -> BuildProgressSnapshot:
    build_run = get_build_run(db, build_run_id=build_run_id)
    if build_run is None:
        msg = f"Unknown build_run_id={build_run_id}"
        raise ValueError(msg)
    resolved_section_code = _resolve_section_code(build_run=build_run, section_code=section_code)
    stages = get_build_stages()
    _validate_stage_history_matches_registry(
        db,
        build_run_id=build_run_id,
        section_code=resolved_section_code,
        stages=stages,
    )
    completed_stage_indexes = get_completed_stage_indexes(
        db,
        build_run_id=build_run_id,
        section_code=resolved_section_code,
    )
    if not completed_stage_indexes:
        LOGGER.info(
            "Build progress missing; starting from stage 0 section_code=%s",
            resolved_section_code,
        )
    course_version_id = get_latest_course_version_id_for_build_run(db, build_run=build_run)
    return BuildProgressSnapshot(
        build_run_id=build_run_id,
        build_version=build_run.build_version,
        section_code=resolved_section_code,
        course_version_id=course_version_id,
        next_stage_index=_derived_next_stage_index(
            stages=stages,
            completed_stage_indexes=completed_stage_indexes,
        ),
        last_attempted_stage_name=get_latest_attempted_stage_name(
            db,
            build_run_id=build_run_id,
            section_code=resolved_section_code,
        ),
    )


def _build_context(*, db: Session, config: CourseBuildConfig, course_version_id: str) -> BuildContext:
    course_version = get_course_version(db, course_version_id=course_version_id)
    if course_version is None:
        msg = f"Unknown course_version_id={course_version_id}"
        raise ValueError(msg)
    config_hash = compute_config_hash(config)
    return BuildContext(
        config=config,
        config_hash=config_hash,
        course_version=course_version,
        course_version_id=course_version.id,
        section_code=config.current_section_code,
    )


def _resolve_next_stage_index(*, next_stage_index: int, stages: tuple[BuildStep, ...]) -> int:
    total_stage_count = _total_stage_count(stages)
    if next_stage_index < 0:
        msg = f"Build progress next_stage_index must be >= 0, got {next_stage_index}"
        raise ValueError(msg)
    if next_stage_index >= total_stage_count:
        msg = "All build stages are already completed"
        raise ValueError(msg)
    return next_stage_index


def resolve_next_stage_name(*, db: Session, build_run_id: str, section_code: str | None = None) -> str:
    progress = read_build_progress(db, build_run_id=build_run_id, section_code=section_code)
    stages = get_build_stages()
    next_stage_index = _resolve_next_stage_index(next_stage_index=progress.next_stage_index, stages=stages)
    if next_stage_index == 0:
        return STAGE0_CREATE_COURSE_BUILD
    return stages[next_stage_index - 1].name


def is_build_progress_fully_completed(*, db: Session, build_run_id: str, section_code: str | None = None) -> bool:
    progress = read_build_progress(db, build_run_id=build_run_id, section_code=section_code)
    return progress.next_stage_index == _total_stage_count(get_build_stages())


def is_section_build_fully_completed(
    *,
    db: Session,
    build_version: int,
    config_path: str,
    section_code: str,
) -> bool:
    latest_section_build_run_id = get_latest_section_build_run_id(
        db,
        build_version=build_version,
        config_path=config_path,
        section_code=section_code,
    )
    if latest_section_build_run_id is None:
        return False
    return is_build_progress_fully_completed(
        db=db,
        build_run_id=latest_section_build_run_id,
        section_code=section_code,
    )


def read_latest_section_build_progress(
    *,
    db: Session,
    build_version: int,
    config_path: str,
    section_code: str,
) -> BuildProgressSnapshot | None:
    latest_section_build_run_id = get_latest_section_build_run_id(
        db,
        build_version=build_version,
        config_path=config_path,
        section_code=section_code,
    )
    if latest_section_build_run_id is None:
        return None
    return read_build_progress(
        db,
        build_run_id=latest_section_build_run_id,
        section_code=section_code,
    )


def run_next_build_stage(
    *,
    db: Session,
    config: CourseBuildConfig,
    build_version: int,
    build_run_id: str,
) -> BuildStageRunResult:
    stages = get_build_stages()
    progress = read_build_progress(
        db,
        build_run_id=build_run_id,
        section_code=config.current_section_code,
    )
    next_stage_index = _resolve_next_stage_index(
        next_stage_index=progress.next_stage_index,
        stages=stages,
    )
    config_hash = compute_config_hash(config)

    previous_section_codes = config.previous_section_codes
    if previous_section_codes:
        previous_section_code = previous_section_codes[-1]
        if not is_section_build_fully_completed(
            db=db,
            build_version=build_version,
            config_path=str(config.config_root),
            section_code=previous_section_code,
        ):
            msg = (
                f"Cannot build section {config.current_section_code!r} before previous section "
                f"{previous_section_code!r} is fully completed for build_version={build_version}"
            )
            raise ValueError(msg)

    if next_stage_index == 0:
        existing_course_version = get_existing_course_version_for_build(
            db,
            course_code=config.course.code,
            course_version=config.course.version,
            build_version=build_version,
        )
        LOGGER.info(
            "Running next build stage section_code=%s stage_index=0 stage_name=%s",
            config.current_section_code,
            STAGE0_CREATE_COURSE_BUILD,
        )
        if existing_course_version is None:
            if not config.sections.is_first(config.current_section_code):
                msg = (
                    f"Cannot start section {config.current_section_code!r} for build_version={build_version} "
                    "before the first section has created the course build"
                )
                raise ValueError(msg)
            try:
                course_version = create_draft_build_row(
                    db,
                    config=config,
                    build_version=build_version,
                    config_hash=config_hash,
                )
            except IntegrityError as exc:
                db.rollback()
                msg = (
                    "Failed to create draft course_version row. "
                    "A build with "
                    f"code={config.course.code!r}, version={config.course.version}, "
                    f"and build_version={build_version} may already exist."
                )
                raise ValueError(msg) from exc
        else:
            course_version = existing_course_version
        LOGGER.info(
            "Completed build stage stage_index=0 stage_name=%s remaining_stages=%s",
            STAGE0_CREATE_COURSE_BUILD,
            len(stages),
        )
        LOGGER.info(
            "Resolved course version course_version_id=%s",
            course_version.id,
        )
        result = BuildStageRunResult(
            build_version=build_version,
            course_version_id=course_version.id,
            completed_stage_name=STAGE0_CREATE_COURSE_BUILD,
            completed_stage_index=0,
            remaining_stage_count=len(stages),
        )
    else:
        persisted_course_version = get_existing_course_version_for_build(
            db,
            course_code=config.course.code,
            course_version=config.course.version,
            build_version=build_version,
        )
        if persisted_course_version is None:
            msg = "Build progress indicates completed stage 0, but no course_version row exists"
            raise ValueError(msg)
        course_version_id = persisted_course_version.id
        next_stage = stages[next_stage_index - 1]
        context = _build_context(db=db, config=config, course_version_id=course_version_id)

        LOGGER.info(
            "Running next build stage stage_index=%s stage_name=%s",
            next_stage_index,
            next_stage.name,
        )

        savepoint = db.begin_nested()
        step_db = _CommitDeferredSession(db)
        try:
            next_stage.run(db=cast(Session, step_db), context=context)
            savepoint.commit()
        except Exception:
            with suppress(ResourceClosedError):
                savepoint.rollback()
            db.rollback()
            LOGGER.exception(
                "Failed build stage stage_index=%s stage_name=%s",
                next_stage_index,
                next_stage.name,
            )
            raise

        LOGGER.info(
            "Completed build stage stage_index=%s stage_name=%s remaining_stages=%s",
            next_stage_index,
            next_stage.name,
            len(stages) - next_stage_index,
        )
        result = BuildStageRunResult(
            build_version=build_version,
            course_version_id=course_version_id,
            completed_stage_name=next_stage.name,
            completed_stage_index=next_stage_index,
            remaining_stage_count=len(stages) - next_stage_index,
        )

    db.commit()
    return result
