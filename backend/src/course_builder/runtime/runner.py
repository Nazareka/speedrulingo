from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import ResourceClosedError
from sqlalchemy.orm import Session

from course_builder.config import CourseBuildConfig, CourseBuildConfigLoader
from course_builder.runtime.models import BuildContext, BuildStep, compute_config_hash
from course_builder.runtime.persistence import create_draft_build_row
from course_builder.runtime.stage_registry import get_registered_build_stages
from domain.content.models import CourseBuildCheckpoint, CourseVersion

LOGGER = logging.getLogger(__name__)
STAGE0_CREATE_COURSE_BUILD = "create_course_build"


@dataclass(frozen=True, slots=True)
class BuildCheckpoint:
    build_version: int
    section_code: str
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


def _checkpoint_row(
    db: Session,
    *,
    build_version: int,
    section_code: str,
) -> CourseBuildCheckpoint | None:
    return db.scalar(
        select(CourseBuildCheckpoint).where(
            CourseBuildCheckpoint.build_version == build_version,
            CourseBuildCheckpoint.section_code == section_code,
        )
    )


def read_checkpoint(db: Session, *, build_version: int, section_code: str) -> BuildCheckpoint:
    row = _checkpoint_row(db, build_version=build_version, section_code=section_code)
    if row is None:
        LOGGER.info(
            "Checkpoint missing; starting from stage 0 build_version=%s section_code=%s",
            build_version,
            section_code,
        )
        return BuildCheckpoint(
            build_version=build_version,
            section_code=section_code,
            course_version_id=None,
            next_stage_index=0,
            last_attempted_stage_name=None,
        )
    return BuildCheckpoint(
        build_version=row.build_version,
        section_code=row.section_code,
        course_version_id=row.course_version_id,
        next_stage_index=row.next_stage_index,
        last_attempted_stage_name=row.last_attempted_stage_name,
    )


def write_checkpoint(db: Session, checkpoint: BuildCheckpoint) -> None:
    row = _checkpoint_row(
        db,
        build_version=checkpoint.build_version,
        section_code=checkpoint.section_code,
    )
    if row is None:
        db.add(
            CourseBuildCheckpoint(
                build_version=checkpoint.build_version,
                section_code=checkpoint.section_code,
                course_version_id=checkpoint.course_version_id,
                next_stage_index=checkpoint.next_stage_index,
                last_attempted_stage_name=checkpoint.last_attempted_stage_name,
            )
        )
        db.flush()
        return
    row.course_version_id = checkpoint.course_version_id
    row.next_stage_index = checkpoint.next_stage_index
    row.last_attempted_stage_name = checkpoint.last_attempted_stage_name
    db.flush()


def mark_checkpoint_attempt(
    db: Session,
    *,
    build_version: int,
    section_code: str,
    stage_name: str,
) -> None:
    checkpoint = read_checkpoint(db, build_version=build_version, section_code=section_code)
    write_checkpoint(
        db,
        BuildCheckpoint(
            build_version=checkpoint.build_version,
            section_code=checkpoint.section_code,
            course_version_id=checkpoint.course_version_id,
            next_stage_index=checkpoint.next_stage_index,
            last_attempted_stage_name=stage_name,
        ),
    )


def _build_context(*, db: Session, config: CourseBuildConfig, course_version_id: str) -> BuildContext:
    course_version = db.get(CourseVersion, course_version_id)
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
        msg = f"Checkpoint next_stage_index must be >= 0, got {next_stage_index}"
        raise ValueError(msg)
    if next_stage_index >= total_stage_count:
        msg = "All build stages are already completed"
        raise ValueError(msg)
    return next_stage_index


def resolve_next_stage_name(*, db: Session, build_version: int, section_code: str) -> str:
    checkpoint = read_checkpoint(db, build_version=build_version, section_code=section_code)
    stages = get_build_stages()
    next_stage_index = _resolve_next_stage_index(next_stage_index=checkpoint.next_stage_index, stages=stages)
    if next_stage_index == 0:
        return STAGE0_CREATE_COURSE_BUILD
    return stages[next_stage_index - 1].name


def is_checkpoint_fully_completed(*, db: Session, build_version: int, section_code: str) -> bool:
    checkpoint = read_checkpoint(db, build_version=build_version, section_code=section_code)
    return checkpoint.next_stage_index == _total_stage_count(get_build_stages())


def run_next_build_stage(
    *,
    db: Session,
    config: CourseBuildConfig,
    build_version: int,
) -> BuildStageRunResult:
    stages = get_build_stages()
    checkpoint = read_checkpoint(db, build_version=build_version, section_code=config.current_section_code)
    next_stage_index = _resolve_next_stage_index(
        next_stage_index=checkpoint.next_stage_index,
        stages=stages,
    )
    config_hash = compute_config_hash(config)

    previous_section_codes = config.previous_section_codes
    if previous_section_codes:
        previous_section_code = previous_section_codes[-1]
        if not is_checkpoint_fully_completed(
            db=db,
            build_version=build_version,
            section_code=previous_section_code,
        ):
            msg = (
                f"Cannot build section {config.current_section_code!r} before previous section "
                f"{previous_section_code!r} is fully completed for build_version={build_version}"
            )
            raise ValueError(msg)

    if next_stage_index == 0:
        existing_course_version = db.scalar(
            select(CourseVersion).where(
                CourseVersion.code == config.course.code,
                CourseVersion.version == config.course.version,
                CourseVersion.build_version == build_version,
            )
        )
        LOGGER.info(
            "Running next build stage build_version=%s section_code=%s stage_index=0 stage_name=%s",
            build_version,
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
            course_version = create_draft_build_row(
                db,
                config=config,
                build_version=build_version,
                config_hash=config_hash,
            )
        else:
            course_version = existing_course_version
        updated_checkpoint = BuildCheckpoint(
            build_version=build_version,
            section_code=config.current_section_code,
            course_version_id=course_version.id,
            next_stage_index=1,
            last_attempted_stage_name=STAGE0_CREATE_COURSE_BUILD,
        )
        LOGGER.info(
            "Completed build stage course_version_id=%s build_version=%s stage_index=0 stage_name=%s remaining_stages=%s",
            course_version.id,
            build_version,
            STAGE0_CREATE_COURSE_BUILD,
            len(stages),
        )
        result = BuildStageRunResult(
            build_version=build_version,
            course_version_id=course_version.id,
            completed_stage_name=STAGE0_CREATE_COURSE_BUILD,
            completed_stage_index=0,
            remaining_stage_count=len(stages),
        )
    else:
        course_version_id = checkpoint.course_version_id
        if course_version_id is None:
            msg = "Checkpoint missing course_version_id after completed stage 0"
            raise ValueError(msg)
        next_stage = stages[next_stage_index - 1]
        context = _build_context(db=db, config=config, course_version_id=course_version_id)

        LOGGER.info(
            "Running next build stage course_version_id=%s build_version=%s stage_index=%s stage_name=%s",
            course_version_id,
            build_version,
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
                "Failed build stage course_version_id=%s build_version=%s stage_index=%s stage_name=%s",
                course_version_id,
                build_version,
                next_stage_index,
                next_stage.name,
            )
            raise

        updated_checkpoint = BuildCheckpoint(
            build_version=build_version,
            section_code=config.current_section_code,
            course_version_id=course_version_id,
            next_stage_index=next_stage_index + 1,
            last_attempted_stage_name=next_stage.name,
        )
        LOGGER.info(
            "Completed build stage course_version_id=%s build_version=%s stage_index=%s stage_name=%s remaining_stages=%s",
            course_version_id,
            build_version,
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

    write_checkpoint(db, updated_checkpoint)
    db.commit()
    return result
