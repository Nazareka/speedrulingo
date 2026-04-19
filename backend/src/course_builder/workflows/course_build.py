from __future__ import annotations

from pathlib import Path
from typing import cast

from dbos import DBOS

from course_builder.build_runs.models import (
    AllSectionsBuildSummary,
    BuildRequest,
    SectionBuildSummary,
)
from course_builder.engine.orchestration import CourseBuildOrchestrator, SectionRunner
from course_builder.engine.runner import BuildStageRunResult


@DBOS.step()
def run_one_stage_step(
    *,
    config: str,
    build_version: int,
    section_code: str,
    build_run_id: str | None = None,
    stage_name: str | None = None,
) -> BuildStageRunResult:
    orchestrator = CourseBuildOrchestrator()
    return orchestrator.run_one_stage(
        config_path=Path(config),
        section_code=section_code,
        build_version=build_version,
        build_run_id=build_run_id,
        stage_name=stage_name,
    )


def _run_section_with_dbos_steps(
    request: BuildRequest,
    *,
    build_run_id: str | None = None,
    resume_from_build_run_id: str | None = None,
    parent_build_run_id: str | None = None,
    workflow_id: str | None = None,
) -> SectionBuildSummary:
    def dbos_stage_runner(
        *,
        config_path: Path,
        build_version: int,
        section_code: str,
        build_run_id: str | None = None,
        stage_name: str | None = None,
    ) -> BuildStageRunResult:
        return run_one_stage_step(
            config=str(config_path),
            build_version=build_version,
            section_code=section_code,
            build_run_id=build_run_id,
            stage_name=stage_name,
        )

    orchestrator = CourseBuildOrchestrator()
    return orchestrator.run_section_until_done(
        request,
        stage_runner=dbos_stage_runner,
        build_run_id=build_run_id,
        resume_from_build_run_id=resume_from_build_run_id,
        parent_build_run_id=parent_build_run_id,
        workflow_id=workflow_id,
    )


@DBOS.workflow()
def build_section_workflow(
    config: str,
    build_version: int,
    section_code: str,
    all_stages: bool = True,
    resume_from_build_run_id: str | None = None,
) -> SectionBuildSummary:
    return _run_section_with_dbos_steps(
        BuildRequest(
            config=config,
            build_version=build_version,
            section_code=section_code,
            all_stages=all_stages,
            all_sections=False,
        ),
        resume_from_build_run_id=resume_from_build_run_id,
        workflow_id=DBOS.workflow_id,
    )


@DBOS.workflow()
def build_all_sections_workflow(
    config: str,
    build_version: int,
    all_stages: bool = True,
) -> AllSectionsBuildSummary:
    orchestrator = CourseBuildOrchestrator()
    request = BuildRequest(
        config=config,
        build_version=build_version,
        all_stages=all_stages,
        all_sections=True,
    )

    def section_runner(
        section_request: BuildRequest,
        *,
        build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
    ) -> SectionBuildSummary:
        return _run_section_with_dbos_steps(
            section_request,
            build_run_id=build_run_id,
            parent_build_run_id=parent_build_run_id,
            workflow_id=None,
        )

    return orchestrator.run_all_sections_until_done(
        request,
        section_runner=cast(SectionRunner, section_runner),
        workflow_id=DBOS.workflow_id,
    )
