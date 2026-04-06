from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from prefect import flow, get_run_logger, task
from prefect.artifacts import (
    create_markdown_artifact,
    create_progress_artifact,
    create_table_artifact,
    update_progress_artifact,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app_logging import configure_logging
from course_builder.runtime.orchestration import (
    build_langsmith_tracing_context,
    read_declared_section_codes,
    run_build_stage_with_attempt_log,
)
from course_builder.runtime.runner import (
    BuildStageRunResult,
    get_build_stages,
    is_checkpoint_fully_completed,
    load_config_for_step_runner,
    read_checkpoint,
)
from db.engine import SessionLocal

STAGE0_CREATE_COURSE_BUILD = "create_course_build"


def _artifact_key_fragment(value: str) -> str:
    return value.lower().replace("_", "-")


class BuildRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    config: Path
    build_version: int = Field(ge=1)
    section_code: str | None = None
    all_stages: bool = True
    all_sections: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> BuildRequest:
        if not self.all_sections and self.section_code is None:
            msg = "--section-code is required unless --all-sections is used"
            raise ValueError(msg)
        return self


def build_request(
    *,
    config: str | Path,
    build_version: int,
    section_code: str | None = None,
    all_stages: bool = True,
    all_sections: bool = False,
) -> BuildRequest:
    return BuildRequest(
        config=Path(config),
        build_version=build_version,
        section_code=section_code,
        all_stages=all_stages,
        all_sections=all_sections,
    )


class PrefectLogBridgeHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("prefect."):
            return
        try:
            logger = get_run_logger()
        except RuntimeError:
            return
        logger.log(record.levelno, self.format(record))


@task(name="run-next-build-stage", retries=0)
def run_build_stage_task(
    *,
    config_path: Path,
    section_code: str,
    build_version: int,
) -> BuildStageRunResult:
    configure_logging()
    config = load_config_for_step_runner(config_path, section_code=section_code)
    log_bridge = PrefectLogBridgeHandler()
    log_bridge.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    with SessionLocal() as db, build_langsmith_tracing_context(
        build_version=build_version,
        section_code=section_code,
    ):
        return run_build_stage_with_attempt_log(
            db=db,
            config=config,
            build_version=build_version,
            extra_root_handler=log_bridge,
        )


def _remaining_stage_names(*, completed_stage_count: int) -> list[str]:
    expected_order = [STAGE0_CREATE_COURSE_BUILD, *(stage.name for stage in get_build_stages())]
    return expected_order[completed_stage_count:]


def _publish_progress_artifact(
    *,
    artifact_id: UUID | None,
    completed_stage_count: int,
    total_stage_count: int,
    section_code: str,
) -> UUID | None:
    progress = completed_stage_count / total_stage_count if total_stage_count else 1.0
    description = f"Section {section_code} build progress"
    try:
        if artifact_id is None:
            created_artifact_id = create_progress_artifact(progress=progress, description=description)
            if inspect.isawaitable(created_artifact_id):
                msg = "Synchronous flow received an awaitable progress artifact result"
                raise RuntimeError(msg)
            return created_artifact_id
        update_progress_artifact(artifact_id=artifact_id, progress=progress, description=description)
        return artifact_id
    except RuntimeError:
        return artifact_id


def _publish_section_summary_artifacts(
    *,
    summary: dict[str, Any],
) -> None:
    table_row = dict(summary)
    table_row["ran_stages"] = ",".join(summary["ran_stages"])
    markdown = "\n".join(
        [
            f"### Section `{summary['section_code']}`",
            f"- build_version: `{summary['build_version']}`",
            f"- course_version_id: `{summary['course_version_id']}`",
            f"- completed stages in this run: `{summary['ran_stage_count']}`",
            f"- stage names: `{', '.join(summary['ran_stages'])}`",
        ]
    )
    section_key = _artifact_key_fragment(str(summary["section_code"]))
    try:
        create_markdown_artifact(
            key=f"course-build-{summary['build_version']}-{section_key}",
            markdown=markdown,
            description="Course build section summary",
        )
        create_table_artifact(
            key=f"course-build-table-{summary['build_version']}-{section_key}",
            table=[table_row],
            description="Course build section summary",
        )
    except RuntimeError:
        return


def _run_section_build(request: BuildRequest) -> dict[str, Any]:
    if request.section_code is None:
        msg = "Section build requires a section_code"
        raise ValueError(msg)
    logger = get_run_logger()
    with SessionLocal() as db:
        checkpoint = read_checkpoint(
            db,
            build_version=request.build_version,
            section_code=request.section_code,
        )
    remaining_stage_names = _remaining_stage_names(completed_stage_count=checkpoint.completed_stage_count)
    total_stage_count = len(get_build_stages()) + 1
    completed_stage_names: list[str] = []
    progress_artifact_id = _publish_progress_artifact(
        artifact_id=None,
        completed_stage_count=checkpoint.completed_stage_count,
        total_stage_count=total_stage_count,
        section_code=request.section_code,
    )
    logger.info(
        "Starting section build config=%s section=%s build_version=%s remaining_stages=%s",
        request.config,
        request.section_code,
        request.build_version,
        ",".join(remaining_stage_names),
    )
    last_result: BuildStageRunResult | None = None
    max_stage_runs = total_stage_count if request.all_stages else 1
    for _ in range(max_stage_runs):
        last_result = run_build_stage_task(
            config_path=request.config,
            section_code=request.section_code,
            build_version=request.build_version,
        )
        completed_stage_names.append(last_result.completed_stage_name)
        with SessionLocal() as db:
            updated_checkpoint = read_checkpoint(
                db,
                build_version=request.build_version,
                section_code=request.section_code,
            )
        progress_artifact_id = _publish_progress_artifact(
            artifact_id=progress_artifact_id,
            completed_stage_count=updated_checkpoint.completed_stage_count,
            total_stage_count=total_stage_count,
            section_code=request.section_code,
        )
        if not request.all_stages or last_result.remaining_stage_count == 0:
            break
    if last_result is None:
        msg = "Section build did not execute any stages"
        raise RuntimeError(msg)
    summary = {
        "build_version": last_result.build_version,
        "section_code": request.section_code,
        "course_version_id": last_result.course_version_id,
        "completed_stage": last_result.completed_stage_name,
        "completed_stage_index": last_result.completed_stage_index,
        "remaining_stage_count": last_result.remaining_stage_count,
        "ran_stage_count": len(completed_stage_names),
        "ran_stages": completed_stage_names,
    }
    _publish_section_summary_artifacts(summary=summary)
    return summary


@flow(name="course-build-section", log_prints=True, retries=0)
def build_section_flow(
    *,
    config: str,
    build_version: int,
    section_code: str,
    all_stages: bool = True,
) -> dict[str, Any]:
    return _run_section_build(
        build_request(
            config=config,
            build_version=build_version,
            section_code=section_code,
            all_stages=all_stages,
            all_sections=False,
        )
    )


@flow(name="course-build-all-sections", log_prints=True, retries=0)
def build_all_sections_flow(
    *,
    config: str,
    build_version: int,
    all_stages: bool = True,
) -> dict[str, Any]:
    request = build_request(
        config=config,
        build_version=build_version,
        all_stages=all_stages,
        all_sections=True,
    )
    section_codes = read_declared_section_codes(request.config)
    summaries: list[dict[str, Any]] = []
    for section_code in section_codes:
        with SessionLocal() as db:
            if is_checkpoint_fully_completed(
                db=db,
                build_version=request.build_version,
                section_code=section_code,
            ):
                continue
        summary = _run_section_build(
            build_request(
                config=request.config,
                build_version=request.build_version,
                section_code=section_code,
                all_stages=request.all_stages,
                all_sections=False,
            )
        )
        summaries.append(summary)
    if not summaries:
        msg = "No build stages were executed"
        raise ValueError(msg)
    final_summary = {
        "build_version": request.build_version,
        "ran_section_count": len(summaries),
        "ran_sections": list(summaries),
        "last_section": summaries[-1],
    }
    try:
        create_table_artifact(
            key=f"course-build-all-sections-{request.build_version}",
            table=summaries,
            description="Course build multi-section summary",
        )
    except RuntimeError:
        return final_summary
    return final_summary
