from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import json
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
from domain.content.models import CourseVersion

LOGGER = logging.getLogger(__name__)
STAGE0_CREATE_COURSE_BUILD = "create_course_build"


@dataclass(frozen=True, slots=True)
class BuildCheckpoint:
    build_version: int
    section_code: str
    course_version_id: str | None
    completed_stage_names: tuple[str, ...]
    last_attempted_stage_name: str | None = None
    last_attempt_log_lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BuildStageRunResult:
    build_version: int
    course_version_id: str
    completed_stage_name: str
    completed_stage_index: int
    remaining_stage_count: int
    checkpoint_path: Path


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


def default_checkpoint_path(*, config: CourseBuildConfig, build_version: int, section_code: str | None = None) -> Path:
    return Path("build_checkpoints") / (
        f"course_build_{config.course.code}_v{config.course.version}_build{build_version}_{section_code or config.current_section_code}.json"
    )


def load_config_for_step_runner(config_path: Path, *, section_code: str) -> CourseBuildConfig:
    return CourseBuildConfigLoader.load_and_validate(config_path, section_code=section_code)


def read_checkpoint(checkpoint_path: Path, *, build_version: int, section_code: str) -> BuildCheckpoint:
    if not checkpoint_path.exists():
        LOGGER.info(
            "Checkpoint missing; starting from stage 0 path=%s build_version=%s section_code=%s",
            checkpoint_path,
            build_version,
            section_code,
        )
        return BuildCheckpoint(
            build_version=build_version,
            section_code=section_code,
            course_version_id=None,
            completed_stage_names=(),
        )

    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint = BuildCheckpoint(
        build_version=int(payload["build_version"]),
        section_code=str(payload["section_code"]),
        course_version_id=None if payload["course_version_id"] is None else str(payload["course_version_id"]),
        completed_stage_names=tuple(str(name) for name in payload["completed_stage_names"]),
        last_attempted_stage_name=(
            None if payload.get("last_attempted_stage_name") is None else str(payload["last_attempted_stage_name"])
        ),
        last_attempt_log_lines=tuple(str(line) for line in payload.get("last_attempt_log_lines", [])),
    )
    if checkpoint.build_version != build_version:
        msg = f"Checkpoint build_version mismatch: {checkpoint.build_version} != {build_version}"
        raise ValueError(msg)
    if checkpoint.section_code != section_code:
        msg = f"Checkpoint section_code mismatch: {checkpoint.section_code!r} != {section_code!r}"
        raise ValueError(msg)
    return checkpoint


def write_checkpoint(checkpoint_path: Path, checkpoint: BuildCheckpoint) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "build_version": checkpoint.build_version,
                "section_code": checkpoint.section_code,
                "course_version_id": checkpoint.course_version_id,
                "completed_stage_names": list(checkpoint.completed_stage_names),
                "last_attempted_stage_name": checkpoint.last_attempted_stage_name,
                "last_attempt_log_lines": list(checkpoint.last_attempt_log_lines),
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
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


def _resolve_next_stage_index(*, completed_stage_names: tuple[str, ...], stages: tuple[BuildStep, ...]) -> int:
    expected_order = (STAGE0_CREATE_COURSE_BUILD, *(stage.name for stage in stages))
    expected_prefix = expected_order[: len(completed_stage_names)]
    if completed_stage_names != expected_prefix:
        msg = (
            "Checkpoint completed stages do not match the expected build order: "
            f"{list(completed_stage_names)!r} != {list(expected_prefix)!r}"
        )
        raise ValueError(msg)
    if len(completed_stage_names) >= len(expected_order):
        msg = "All build stages are already completed"
        raise ValueError(msg)
    return len(completed_stage_names)


def resolve_next_stage_name(*, checkpoint_path: Path, build_version: int, section_code: str) -> str:
    checkpoint = read_checkpoint(checkpoint_path, build_version=build_version, section_code=section_code)
    stages = get_build_stages()
    next_stage_index = _resolve_next_stage_index(completed_stage_names=checkpoint.completed_stage_names, stages=stages)
    if next_stage_index == 0:
        return STAGE0_CREATE_COURSE_BUILD
    return stages[next_stage_index - 1].name


def is_checkpoint_fully_completed(*, checkpoint_path: Path, build_version: int, section_code: str) -> bool:
    checkpoint = read_checkpoint(checkpoint_path, build_version=build_version, section_code=section_code)
    expected_completed = (STAGE0_CREATE_COURSE_BUILD, *(stage.name for stage in get_build_stages()))
    return checkpoint.completed_stage_names == expected_completed


def write_checkpoint_attempt_log(
    checkpoint_path: Path,
    *,
    build_version: int,
    section_code: str,
    stage_name: str,
    log_lines: list[str],
) -> None:
    checkpoint = read_checkpoint(checkpoint_path, build_version=build_version, section_code=section_code)
    write_checkpoint(
        checkpoint_path,
        BuildCheckpoint(
            build_version=checkpoint.build_version,
            section_code=checkpoint.section_code,
            course_version_id=checkpoint.course_version_id,
            completed_stage_names=checkpoint.completed_stage_names,
            last_attempted_stage_name=stage_name,
            last_attempt_log_lines=tuple(log_lines),
        ),
    )


def run_next_build_stage(
    *,
    db: Session,
    config: CourseBuildConfig,
    build_version: int,
    checkpoint_path: Path,
) -> BuildStageRunResult:
    stages = get_build_stages()
    checkpoint = read_checkpoint(checkpoint_path, build_version=build_version, section_code=config.current_section_code)
    next_stage_index = _resolve_next_stage_index(
        completed_stage_names=checkpoint.completed_stage_names,
        stages=stages,
    )
    config_hash = compute_config_hash(config)

    previous_section_codes = config.previous_section_codes
    if previous_section_codes:
        previous_section_code = previous_section_codes[-1]
        previous_checkpoint_path = default_checkpoint_path(
            config=config,
            build_version=build_version,
            section_code=previous_section_code,
        )
        previous_checkpoint = read_checkpoint(
            previous_checkpoint_path,
            build_version=build_version,
            section_code=previous_section_code,
        )
        expected_completed = (STAGE0_CREATE_COURSE_BUILD, *(stage.name for stage in stages))
        if previous_checkpoint.completed_stage_names != expected_completed:
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
            "Running next build stage build_version=%s section_code=%s stage_index=0 stage_name=%s checkpoint=%s",
            build_version,
            config.current_section_code,
            STAGE0_CREATE_COURSE_BUILD,
            checkpoint_path,
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
            completed_stage_names=(STAGE0_CREATE_COURSE_BUILD,),
        )
        write_checkpoint(checkpoint_path, updated_checkpoint)
        LOGGER.info(
            "Completed build stage course_version_id=%s build_version=%s stage_index=0 stage_name=%s remaining_stages=%s checkpoint=%s",
            course_version.id,
            build_version,
            STAGE0_CREATE_COURSE_BUILD,
            len(stages),
            checkpoint_path,
        )
        return BuildStageRunResult(
            build_version=build_version,
            course_version_id=course_version.id,
            completed_stage_name=STAGE0_CREATE_COURSE_BUILD,
            completed_stage_index=0,
            remaining_stage_count=len(stages),
            checkpoint_path=checkpoint_path,
        )

    course_version_id = checkpoint.course_version_id
    if course_version_id is None:
        msg = "Checkpoint missing course_version_id after completed stage 0"
        raise ValueError(msg)
    next_stage = stages[next_stage_index - 1]
    context = _build_context(db=db, config=config, course_version_id=course_version_id)

    LOGGER.info(
        "Running next build stage course_version_id=%s build_version=%s stage_index=%s stage_name=%s checkpoint=%s",
        course_version_id,
        build_version,
        next_stage_index,
        next_stage.name,
        checkpoint_path,
    )

    savepoint = db.begin_nested()
    step_db = _CommitDeferredSession(db)
    try:
        next_stage.run(db=cast(Session, step_db), context=context)
        savepoint.commit()
        db.commit()
    except Exception:
        with suppress(ResourceClosedError):
            savepoint.rollback()
        db.rollback()
        LOGGER.exception(
            "Failed build stage course_version_id=%s build_version=%s stage_index=%s stage_name=%s checkpoint=%s",
            course_version_id,
            build_version,
            next_stage_index,
            next_stage.name,
            checkpoint_path,
        )
        raise

    updated_checkpoint = BuildCheckpoint(
        build_version=build_version,
        section_code=config.current_section_code,
        course_version_id=course_version_id,
        completed_stage_names=(*checkpoint.completed_stage_names, next_stage.name),
    )
    write_checkpoint(checkpoint_path, updated_checkpoint)

    LOGGER.info(
        "Completed build stage course_version_id=%s build_version=%s stage_index=%s stage_name=%s remaining_stages=%s checkpoint=%s",
        course_version_id,
        build_version,
        next_stage_index,
        next_stage.name,
        len(stages) - next_stage_index,
        checkpoint_path,
    )

    return BuildStageRunResult(
        build_version=build_version,
        course_version_id=course_version_id,
        completed_stage_name=next_stage.name,
        completed_stage_index=next_stage_index,
        remaining_stage_count=len(stages) - next_stage_index,
        checkpoint_path=checkpoint_path,
    )
