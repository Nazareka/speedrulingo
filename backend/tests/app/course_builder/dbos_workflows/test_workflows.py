from __future__ import annotations

from typing import Any

import pytest

from course_builder.runtime import AllSectionsBuildSummary, BuildRequest, SectionBuildSummary
from course_builder.runtime.dbos import build_all_sections_workflow, build_section_workflow
from course_builder.runtime.runner import BuildStageRunResult


def test_build_section_workflow_uses_dbos_workflow_id_and_stage_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    class FakeDBOS:
        workflow_id = "workflow-123"

    def fake_run_one_stage_step(
        *,
        config: str,
        build_version: int,
        section_code: str,
        build_run_id: str | None = None,
        stage_name: str | None = None,
    ) -> BuildStageRunResult:
        calls["stage_step"] = {
            "config": config,
            "build_version": build_version,
            "section_code": section_code,
            "build_run_id": build_run_id,
            "stage_name": stage_name,
        }
        return BuildStageRunResult(
            build_version=build_version,
            course_version_id="course-version-1",
            completed_stage_name="create_course_build",
            completed_stage_index=0,
            remaining_stage_count=7,
        )

    def fake_run_section_until_done(
        self: object,
        request: BuildRequest,
        *,
        stage_runner: Any,
        build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
    ) -> SectionBuildSummary:
        assert request.section_code is not None
        calls["request"] = request
        calls["build_run_id"] = build_run_id
        calls["parent_build_run_id"] = parent_build_run_id
        calls["workflow_id"] = workflow_id
        calls["stage_result"] = stage_runner(
            config_path=request.config,
            build_version=request.build_version,
            section_code=request.section_code,
        )
        return {
            "build_run_id": "run-1",
            "build_version": request.build_version,
            "section_code": request.section_code,
            "course_version_id": "course-version-1",
            "completed_stage": "create_course_build",
            "completed_stage_index": 0,
            "remaining_stage_count": 7,
            "ran_stage_count": 1,
            "ran_stages": ["create_course_build"],
            "was_noop": False,
        }

    monkeypatch.setattr("course_builder.runtime.dbos.DBOS", FakeDBOS)
    monkeypatch.setattr("course_builder.runtime.dbos.run_one_stage_step", fake_run_one_stage_step)
    monkeypatch.setattr(
        "course_builder.runtime.dbos.CourseBuildOrchestrator.run_section_until_done",
        fake_run_section_until_done,
    )

    summary = build_section_workflow.__wrapped__(  # type: ignore[attr-defined]  # DBOS preserves the wrapped function.
        config="config/en-ja-v1",
        build_version=9,
        section_code="PRE_A1",
        all_stages=True,
    )

    assert summary["section_code"] == "PRE_A1"
    assert calls["workflow_id"] == "workflow-123"
    assert calls["build_run_id"] is None
    assert calls["parent_build_run_id"] is None
    assert calls["stage_step"] == {
        "config": "config/en-ja-v1",
        "build_version": 9,
        "section_code": "PRE_A1",
        "build_run_id": None,
        "stage_name": None,
    }
    assert calls["stage_result"].completed_stage_name == "create_course_build"


def test_build_all_sections_workflow_passes_section_runner_and_workflow_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    class FakeDBOS:
        workflow_id = "workflow-456"

    def fake_run_section_until_done(
        self: object,
        request: BuildRequest,
        *,
        stage_runner: Any,
        build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
    ) -> SectionBuildSummary:
        assert request.section_code is not None
        calls["section_request"] = request
        calls["section_build_run_id"] = build_run_id
        calls["section_parent_build_run_id"] = parent_build_run_id
        calls["section_workflow_id"] = workflow_id
        return {
            "build_run_id": build_run_id or "section-run-1",
            "build_version": request.build_version,
            "section_code": request.section_code,
            "course_version_id": "course-version-1",
            "completed_stage": "bootstrap_catalog",
            "completed_stage_index": 1,
            "remaining_stage_count": 6,
            "ran_stage_count": 1,
            "ran_stages": ["bootstrap_catalog"],
            "was_noop": False,
        }

    def fake_run_all_sections_until_done(
        self: object,
        request: BuildRequest,
        *,
        section_runner: Any,
        workflow_id: str | None = None,
    ) -> AllSectionsBuildSummary:
        calls["all_sections_request"] = request
        calls["all_sections_workflow_id"] = workflow_id
        section_summary = section_runner(
            request.model_copy(update={"section_code": "PRE_A1", "all_sections": False}),
            parent_build_run_id="build-run-parent",
        )
        calls["section_summary"] = section_summary
        return {
            "build_run_id": "build-run-parent",
            "build_version": request.build_version,
            "ran_section_count": 1,
            "ran_sections": [section_summary],
            "last_section": section_summary,
            "was_noop": False,
        }

    monkeypatch.setattr("course_builder.runtime.dbos.DBOS", FakeDBOS)
    monkeypatch.setattr(
        "course_builder.runtime.dbos.CourseBuildOrchestrator.run_section_until_done",
        fake_run_section_until_done,
    )
    monkeypatch.setattr(
        "course_builder.runtime.dbos.CourseBuildOrchestrator.run_all_sections_until_done",
        fake_run_all_sections_until_done,
    )

    summary = build_all_sections_workflow.__wrapped__(  # type: ignore[attr-defined]  # DBOS preserves the wrapped function.
        config="config/en-ja-v1",
        build_version=12,
        all_stages=True,
    )

    assert summary["build_run_id"] == "build-run-parent"
    assert calls["all_sections_workflow_id"] == "workflow-456"
    assert calls["section_build_run_id"] is None
    assert calls["section_parent_build_run_id"] == "build-run-parent"
    assert calls["section_workflow_id"] is None
    assert calls["section_summary"]["section_code"] == "PRE_A1"
