from __future__ import annotations

from sqlalchemy.orm import Session

from course_builder.build_runs.queries import (
    get_build_run,
    get_build_run_by_workflow_id,
    list_build_runs,
    list_log_events,
    list_stage_runs,
)
from domain.content.models import CourseBuildLogEvent, CourseBuildRun, CourseBuildStageRun


def test_build_queries_return_runs_stages_and_logs_in_ui_order(db_session: Session) -> None:
    older_run = CourseBuildRun(
        workflow_id="workflow-1",
        build_version=10,
        config_path="config/en-ja-v1",
        scope_kind="section",
        section_code="PRE_A1",
        status="completed",
        all_stages=True,
        total_stage_count=8,
    )
    newer_run = CourseBuildRun(
        workflow_id="workflow-2",
        build_version=11,
        config_path="config/en-ja-v1",
        scope_kind="section",
        section_code="A1_1",
        status="running",
        all_stages=True,
        total_stage_count=8,
    )
    child_run = CourseBuildRun(
        parent_build_run_id=newer_run.id,
        build_version=11,
        config_path="config/en-ja-v1",
        scope_kind="section",
        section_code="A1_2",
        status="running",
        all_stages=True,
        total_stage_count=8,
    )
    db_session.add_all([older_run, newer_run])
    db_session.flush()
    child_run.parent_build_run_id = newer_run.id
    db_session.add(child_run)

    db_session.add_all(
        [
            CourseBuildStageRun(
                build_run_id=newer_run.id,
                section_code="A1_1",
                stage_name="pattern_vocab_generation",
                stage_index=2,
                status="completed",
            ),
            CourseBuildStageRun(
                build_run_id=newer_run.id,
                section_code="A1_1",
                stage_name="bootstrap_catalog",
                stage_index=1,
                status="completed",
            ),
            CourseBuildLogEvent(
                build_run_id=newer_run.id,
                section_code="A1_1",
                stage_name="bootstrap_catalog",
                level="INFO",
                message="first log line",
            ),
            CourseBuildLogEvent(
                build_run_id=newer_run.id,
                section_code="A1_1",
                stage_name="pattern_vocab_generation",
                level="INFO",
                message="second log line",
            ),
        ]
    )
    db_session.commit()

    runs = list_build_runs(db_session)
    selected_run = get_build_run(db_session, build_run_id=newer_run.id)
    stage_runs = list_stage_runs(db_session, build_run_id=newer_run.id)
    log_events = list_log_events(db_session, build_run_id=newer_run.id)

    assert [run.id for run in runs] == [newer_run.id, older_run.id]
    assert selected_run is not None
    assert selected_run.id == newer_run.id
    assert [stage.stage_name for stage in stage_runs] == [
        "bootstrap_catalog",
        "pattern_vocab_generation",
    ]
    assert [event.message for event in log_events] == [
        "first log line",
        "second log line",
    ]


def test_get_build_run_by_workflow_id_returns_only_top_level_run(db_session: Session) -> None:
    parent_run = CourseBuildRun(
        workflow_id="workflow-shared",
        build_version=10,
        config_path="config/en-ja-v1",
        scope_kind="all_sections",
        status="running",
        all_stages=True,
        total_stage_count=16,
    )
    child_run = CourseBuildRun(
        parent_build_run_id=parent_run.id,
        workflow_id="workflow-shared",
        build_version=10,
        config_path="config/en-ja-v1",
        scope_kind="section",
        section_code="PRE_A1",
        status="running",
        all_stages=True,
        total_stage_count=8,
    )
    db_session.add(parent_run)
    db_session.flush()
    child_run.parent_build_run_id = parent_run.id
    db_session.add(child_run)
    db_session.commit()

    selected_run = get_build_run_by_workflow_id(db_session, workflow_id="workflow-shared")

    assert selected_run is not None
    assert selected_run.id == parent_run.id
