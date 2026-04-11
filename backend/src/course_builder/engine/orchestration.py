from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager, nullcontext
import logging
from pathlib import Path
from typing import Any, Protocol, cast

from langsmith import Client, tracing_context
from sqlalchemy.orm import Session
import yaml

from course_builder.build_runs.log_handlers import BuildRunLogHandler, FanoutHandler
from course_builder.build_runs.models import AllSectionsBuildSummary, BuildRequest, SectionBuildSummary
from course_builder.build_runs.tracking import BuildRunTracking
from course_builder.config import CourseBuildConfig
from course_builder.engine.runner import (
    BuildProgressSnapshot,
    BuildStageRunResult,
    get_build_stages,
    is_section_build_fully_completed,
    load_config_for_step_runner,
    read_build_progress,
    read_latest_section_build_progress,
    run_next_build_stage,
)
from db.engine import SessionLocal
from settings import get_settings

STAGE0_CREATE_COURSE_BUILD = "create_course_build"


class SectionProgressReporter(Protocol):
    def __call__(self, progress: BuildProgressSnapshot) -> None: ...


class SectionSummaryReporter(Protocol):
    def __call__(self, summary: SectionBuildSummary) -> None: ...


LoggerLike = logging.Logger | logging.LoggerAdapter[Any] | None


class SectionRunner(Protocol):
    def __call__(
        self,
        request: BuildRequest,
        *,
        build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
    ) -> SectionBuildSummary: ...


class StageRunner(Protocol):
    def __call__(
        self,
        *,
        config_path: Path,
        section_code: str,
        build_version: int,
        build_run_id: str | None = None,
        stage_name: str | None = None,
    ) -> BuildStageRunResult: ...


def build_langsmith_tracing_context(*, build_version: int, section_code: str) -> AbstractContextManager[object]:
    settings = get_settings()
    if not settings.langsmith_tracing:
        return nullcontext()
    api_key = settings.langsmith_api_key
    project_name = settings.langsmith_project
    if api_key is None or project_name is None:
        msg = "LANGSMITH_TRACING is enabled but LangSmith credentials are incomplete in settings"
        raise ValueError(msg)
    client = Client(
        api_key=api_key.get_secret_value(),
        api_url=settings.langsmith_endpoint,
    )
    return tracing_context(
        enabled=True,
        client=client,
        project_name=project_name,
        tags=["course_build", "orchestrator", f"section:{section_code}"],
        metadata={"build_version": build_version, "section_code": section_code},
    )


def read_declared_section_codes(config_root: Path) -> list[str]:
    payload = yaml.safe_load((config_root / "course.yaml").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Config file must contain a mapping at root level: {config_root / 'course.yaml'}"
        raise ValueError(msg)
    section_codes = payload.get("sections")
    if not isinstance(section_codes, list) or not section_codes or not all(isinstance(code, str) for code in section_codes):
        msg = "course.yaml must declare a non-empty string sections list"
        raise ValueError(msg)
    return list(section_codes)


def _remaining_stage_names(*, completed_stage_count: int) -> list[str]:
    expected_order = [STAGE0_CREATE_COURSE_BUILD, *(stage.name for stage in get_build_stages())]
    return expected_order[completed_stage_count:]


def _next_stage_name(*, completed_stage_count: int) -> str | None:
    remaining = _remaining_stage_names(completed_stage_count=completed_stage_count)
    return remaining[0] if remaining else None


def _last_completed_stage_name(*, completed_stage_count: int) -> str | None:
    if completed_stage_count <= 0:
        return None
    expected_order = [STAGE0_CREATE_COURSE_BUILD, *(stage.name for stage in get_build_stages())]
    return expected_order[completed_stage_count - 1]


@contextmanager
def root_log_handler_context(handler: logging.Handler | None) -> Any:
    root_logger = logging.getLogger()
    previous_root_level = root_logger.level
    should_restore_level = previous_root_level > logging.INFO
    should_attach_handler = handler is not None and handler not in root_logger.handlers
    if handler is not None and should_attach_handler:
        root_logger.addHandler(handler)
    if should_restore_level:
        root_logger.setLevel(logging.INFO)
    try:
        yield
    finally:
        if should_restore_level:
            root_logger.setLevel(previous_root_level)
        if handler is not None and should_attach_handler:
            root_logger.removeHandler(handler)


def run_build_stage_with_attempt_log(
    *,
    db: Session,
    config: CourseBuildConfig,
    build_version: int,
    build_run_id: str | None = None,
    extra_root_handler: logging.Handler | None = None,
) -> BuildStageRunResult:
    if build_run_id is None:
        msg = "build_run_id is required for stage execution"
        raise ValueError(msg)
    with root_log_handler_context(extra_root_handler):
        return run_next_build_stage(
            db=db,
            config=config,
            build_version=build_version,
            build_run_id=build_run_id,
        )


class CourseBuildOrchestrator:
    @staticmethod
    def _read_all_sections_completed_stage_count(
        *,
        build_version: int,
        config_path: Path,
        section_codes: list[str],
    ) -> int:
        with SessionLocal() as db:
            return sum(
                progress.completed_stage_count
                for section_code in section_codes
                if (
                    progress := read_latest_section_build_progress(
                        db=db,
                        build_version=build_version,
                        config_path=str(config_path),
                        section_code=section_code,
                    )
                )
                is not None
            )

    @staticmethod
    def cancel_build_run(*, build_run_id: str) -> None:
        BuildRunTracking.cancel_build_run(build_run_id=build_run_id)

    @staticmethod
    def run_one_stage(
        *,
        config_path: Path,
        section_code: str,
        build_version: int,
        build_run_id: str | None = None,
        stage_name: str | None = None,
        extra_root_handler: logging.Handler | None = None,
    ) -> BuildStageRunResult:
        config = load_config_for_step_runner(config_path, section_code=section_code)
        persistent_handler = (
            BuildRunLogHandler(
                build_run_id=build_run_id,
                section_code=section_code,
                stage_name=stage_name,
                session_factory=SessionLocal,
            )
            if build_run_id is not None and stage_name is not None
            else None
        )
        handler = (
            FanoutHandler(persistent_handler, extra_root_handler)
            if persistent_handler is not None and extra_root_handler is not None
            else persistent_handler or extra_root_handler
        )
        with (
            SessionLocal() as db,
            build_langsmith_tracing_context(
                build_version=build_version,
                section_code=section_code,
            ),
            root_log_handler_context(handler),
        ):
            return run_build_stage_with_attempt_log(
                db=db,
                config=config,
                build_version=build_version,
                build_run_id=build_run_id,
                extra_root_handler=handler,
            )

    @staticmethod
    def read_build_progress(*, build_run_id: str, section_code: str | None = None) -> BuildProgressSnapshot:
        with SessionLocal() as db:
            return read_build_progress(
                db,
                build_run_id=build_run_id,
                section_code=section_code,
            )

    @staticmethod
    def is_section_completed(*, build_version: int, config_path: Path, section_code: str) -> bool:
        with SessionLocal() as db:
            return is_section_build_fully_completed(
                db=db,
                build_version=build_version,
                config_path=str(config_path),
                section_code=section_code,
            )

    def run_section_until_done(
        self,
        request: BuildRequest,
        *,
        logger: LoggerLike = None,
        stage_runner: StageRunner | None = None,
        progress_reporter: SectionProgressReporter | None = None,
        summary_reporter: SectionSummaryReporter | None = None,
        build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
        requested_by: str | None = None,
    ) -> SectionBuildSummary:
        if request.section_code is None:
            msg = "Section build requires a section_code"
            raise ValueError(msg)
        total_stage_count = len(get_build_stages()) + 1
        owns_build_run = build_run_id is None
        active_build_run_id = build_run_id or BuildRunTracking.create_run_row(
            request=request,
            scope_kind="section",
            total_stage_count=total_stage_count,
            parent_build_run_id=parent_build_run_id,
            workflow_id=workflow_id if parent_build_run_id is None else None,
            requested_by=requested_by,
        ).id
        progress = self.read_build_progress(
            build_run_id=active_build_run_id,
            section_code=request.section_code,
        )
        BuildRunTracking.sync_progress(
            build_run_id=active_build_run_id,
            completed_stage_count=progress.completed_stage_count,
            current_stage_name=_next_stage_name(completed_stage_count=progress.completed_stage_count),
        )
        if progress_reporter is not None:
            progress_reporter(progress)
        remaining_stage_names = _remaining_stage_names(completed_stage_count=progress.completed_stage_count)
        start_message = (
            f"Starting section build config={request.config} section={request.section_code} "
            f"build_version={request.build_version} remaining_stages={','.join(remaining_stage_names)}"
        )
        if logger is not None:
            logger.info(start_message)
        BuildRunTracking.log_message(
            build_run_id=active_build_run_id,
            level="INFO",
            message=start_message,
            section_code=request.section_code,
        )
        active_stage_runner = stage_runner or self.run_one_stage
        last_result: BuildStageRunResult | None = None
        completed_stage_names: list[str] = []
        max_stage_runs = total_stage_count if request.all_stages else 1
        for _ in range(max_stage_runs):
            if BuildRunTracking.is_cancelled(build_run_id=active_build_run_id):
                break
            next_stage_index = progress.completed_stage_count
            next_stage_name = _next_stage_name(completed_stage_count=next_stage_index)
            if next_stage_name is None:
                break
            BuildRunTracking.sync_progress(
                build_run_id=active_build_run_id,
                completed_stage_count=next_stage_index,
                current_stage_name=next_stage_name,
            )
            BuildRunTracking.log_message(
                build_run_id=active_build_run_id,
                level="INFO",
                message=f"Running stage {next_stage_name} for section {request.section_code}",
                section_code=request.section_code,
                stage_name=next_stage_name,
            )
            stage_run_id = BuildRunTracking.create_stage_run_row(
                build_run_id=active_build_run_id,
                section_code=request.section_code,
                stage_name=next_stage_name,
                stage_index=next_stage_index,
            )
            try:
                last_result = active_stage_runner(
                    config_path=request.config,
                    section_code=request.section_code,
                    build_version=request.build_version,
                    build_run_id=active_build_run_id,
                    stage_name=next_stage_name,
                )
                completed_stage_names.append(last_result.completed_stage_name)
                BuildRunTracking.mark_stage_completed(stage_run_id=stage_run_id)
                updated_progress = self.read_build_progress(
                    build_run_id=active_build_run_id,
                    section_code=request.section_code,
                )
                progress = updated_progress
                if BuildRunTracking.is_cancelled(build_run_id=active_build_run_id):
                    break
                BuildRunTracking.sync_progress(
                    build_run_id=active_build_run_id,
                    completed_stage_count=updated_progress.completed_stage_count,
                    current_stage_name=_next_stage_name(completed_stage_count=updated_progress.completed_stage_count),
                    course_version_id=last_result.course_version_id,
                )
                BuildRunTracking.log_message(
                    build_run_id=active_build_run_id,
                    level="INFO",
                    message=f"Completed stage {last_result.completed_stage_name} for section {request.section_code}",
                    section_code=request.section_code,
                    stage_name=last_result.completed_stage_name,
                )
                if progress_reporter is not None:
                    progress_reporter(updated_progress)
                if not request.all_stages or last_result.remaining_stage_count == 0:
                    break
            except Exception as exc:
                error_message = str(exc)
                BuildRunTracking.mark_stage_failed(stage_run_id=stage_run_id, error_message=error_message)
                if owns_build_run:
                    BuildRunTracking.mark_failed(
                        build_run_id=active_build_run_id,
                        error_message=error_message,
                        current_stage_name=next_stage_name,
                    )
                BuildRunTracking.log_message(
                    build_run_id=active_build_run_id,
                    level="ERROR",
                    message=f"Failed stage {next_stage_name} for section {request.section_code}: {error_message}",
                    section_code=request.section_code,
                    stage_name=next_stage_name,
                )
                raise
        if last_result is None:
            if owns_build_run:
                BuildRunTracking.mark_completed(
                    build_run_id=active_build_run_id,
                    course_version_id=progress.course_version_id,
                    completed_stage_count=progress.completed_stage_count,
                )
            noop_summary: SectionBuildSummary = {
                "build_run_id": active_build_run_id,
                "build_version": request.build_version,
                "section_code": request.section_code,
                "course_version_id": progress.course_version_id,
                "completed_stage": _last_completed_stage_name(completed_stage_count=progress.completed_stage_count),
                "completed_stage_index": (
                    progress.completed_stage_count - 1 if progress.completed_stage_count > 0 else None
                ),
                "remaining_stage_count": 0,
                "ran_stage_count": 0,
                "ran_stages": [],
                "was_noop": True,
            }
            if summary_reporter is not None:
                summary_reporter(noop_summary)
            return noop_summary
        if owns_build_run:
            BuildRunTracking.mark_completed(
                build_run_id=active_build_run_id,
                course_version_id=last_result.course_version_id,
                completed_stage_count=progress.completed_stage_count,
            )
        summary: SectionBuildSummary = {
            "build_run_id": active_build_run_id,
            "build_version": last_result.build_version,
            "section_code": request.section_code,
            "course_version_id": last_result.course_version_id,
            "completed_stage": last_result.completed_stage_name,
            "completed_stage_index": last_result.completed_stage_index,
            "remaining_stage_count": last_result.remaining_stage_count,
            "ran_stage_count": len(completed_stage_names),
            "ran_stages": completed_stage_names,
            "was_noop": False,
        }
        if summary_reporter is not None:
            summary_reporter(summary)
        return summary

    def run_all_sections_until_done(
        self,
        request: BuildRequest,
        *,
        logger: LoggerLike = None,
        section_runner: SectionRunner | None = None,
        workflow_id: str | None = None,
        requested_by: str | None = None,
    ) -> AllSectionsBuildSummary:
        section_codes = read_declared_section_codes(request.config)
        total_stage_count = (len(get_build_stages()) + 1) * len(section_codes)
        build_run = BuildRunTracking.create_run_row(
            request=request,
            scope_kind="all_sections",
            total_stage_count=total_stage_count,
            workflow_id=workflow_id,
            requested_by=requested_by,
        )
        initial_completed_stage_count = self._read_all_sections_completed_stage_count(
            build_version=request.build_version,
            config_path=request.config,
            section_codes=section_codes,
        )
        BuildRunTracking.sync_progress(
            build_run_id=build_run.id,
            completed_stage_count=initial_completed_stage_count,
            current_stage_name=None,
        )
        summaries: list[SectionBuildSummary] = []
        active_section_runner: SectionRunner
        if section_runner is None:
            def default_section_runner(
                section_request: BuildRequest,
                *,
                build_run_id: str | None = None,
                parent_build_run_id: str | None = None,
            ) -> SectionBuildSummary:
                return self.run_section_until_done(
                    section_request,
                    logger=logger,
                    build_run_id=build_run_id,
                    parent_build_run_id=parent_build_run_id,
                )
            active_section_runner = cast(SectionRunner, default_section_runner)
        else:
            active_section_runner = section_runner
        for section_code in section_codes:
            if BuildRunTracking.is_cancelled(build_run_id=build_run.id):
                break
            if self.is_section_completed(
                build_version=request.build_version,
                config_path=request.config,
                section_code=section_code,
            ):
                continue
            BuildRunTracking.sync_progress(
                build_run_id=build_run.id,
                completed_stage_count=self._read_all_sections_completed_stage_count(
                    build_version=request.build_version,
                    config_path=request.config,
                    section_codes=section_codes,
                ),
                current_stage_name=section_code,
            )
            try:
                summary = active_section_runner(
                    request.model_copy(update={"section_code": section_code, "all_sections": False}),
                    parent_build_run_id=build_run.id,
                )
                summaries.append(summary)
                if BuildRunTracking.is_cancelled(build_run_id=build_run.id):
                    break
            except Exception as exc:
                BuildRunTracking.mark_failed(
                    build_run_id=build_run.id,
                    error_message=str(exc),
                    current_stage_name=section_code,
                )
                raise
            completed_stage_count = self._read_all_sections_completed_stage_count(
                build_version=request.build_version,
                config_path=request.config,
                section_codes=section_codes,
            )
            BuildRunTracking.sync_progress(
                build_run_id=build_run.id,
                completed_stage_count=completed_stage_count,
                current_stage_name=section_code,
            )
        if not summaries:
            BuildRunTracking.mark_completed(
                build_run_id=build_run.id,
                course_version_id=None,
                completed_stage_count=initial_completed_stage_count,
            )
            return {
                "build_run_id": build_run.id,
                "build_version": request.build_version,
                "ran_section_count": 0,
                "ran_sections": [],
                "last_section": None,
                "was_noop": True,
            }
        final_completed_stage_count = self._read_all_sections_completed_stage_count(
            build_version=request.build_version,
            config_path=request.config,
            section_codes=section_codes,
        )
        BuildRunTracking.mark_completed(
            build_run_id=build_run.id,
            course_version_id=summaries[-1]["course_version_id"],
            completed_stage_count=final_completed_stage_count,
        )
        return {
            "build_run_id": build_run.id,
            "build_version": request.build_version,
            "ran_section_count": len(summaries),
            "ran_sections": summaries,
            "last_section": summaries[-1],
            "was_noop": False,
        }
